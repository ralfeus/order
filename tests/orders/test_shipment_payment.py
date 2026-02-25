"""Tests for the SeparateShipping payment flow (API + client routes)"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.models import Country
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.shipping.methods.separate.models.separate_shipping import SeparateShipping
from app.shipping.models.shipping import NoShipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User

PW_HASH = "pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576"
# EUR rate used in tests – 5000 KRW * 0.001 = 5 EUR (kept small for easy arithmetic)
EUR_RATE = 0.001
SHIPPING_KRW = 5000
SHIPPING_EUR = SHIPPING_KRW * EUR_RATE   # 5.0


def _make_intent(status='succeeded', order_id=None):
    intent = MagicMock()
    intent.status = status
    intent.metadata = {'order_id': order_id or ''}
    intent.latest_charge = None
    intent.client_secret = 'test_client_secret'
    intent.id = 'pi_test_123'
    return intent


class TestShipmentPaymentApi(BaseTestCase):
    """Tests for POST /api/v1/order/<id>/shipment/pay"""

    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name='admin')
        self.user = User(
            username='user_test_shipment_api',
            email='user_shipment_api@test.com',
            password_hash=PW_HASH,
            enabled=True,
        )
        self.admin = User(
            username='admin_test_shipment_api',
            email='admin_shipment_api@test.com',
            password_hash=PW_HASH,
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=EUR_RATE),
            Country(id='c1', name='Country1'),
            SeparateShipping(id=1, name='Separate Shipping'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=SHIPPING_KRW),
            NoShipping(id=999),
        ])

        gen_id = f'ORD-pay-api-{int(datetime.now().timestamp())}'
        self.order = Order(
            id=gen_id,
            user=self.user,
            country_id='c1',
            shipping=SeparateShipping.query.get(1),
            status=OrderStatus.packed,
            subtotal_krw=10000,
            shipping_krw=SHIPPING_KRW,
            shipping_cur2=SHIPPING_EUR,
            total_weight=500,
        )
        self.try_add_entity(self.order)

    # ------------------------------------------------------------------
    # Unauthenticated / auth guard
    # ------------------------------------------------------------------

    def test_unauthenticated_request_redirects(self):
        res = self.client.post(
            f'/api/v1/order/{self.order.id}/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )
        self.assertEqual(res.status_code, 302)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    @patch('stripe.PaymentMethod.retrieve')
    @patch('stripe.PaymentIntent.create')
    def test_returns_client_secret_for_packed_separate_shipping_order(
            self, mock_create, mock_retrieve):
        mock_retrieve.return_value = MagicMock()
        mock_create.return_value = _make_intent()

        res = self.try_user_operation(
            lambda: self.client.post(
                f'/api/v1/order/{self.order.id}/shipment/pay',
                json={'payment_method_id': 'pm_test'},
            )
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('client_secret', res.json)
        self.assertEqual(res.json['client_secret'], 'test_client_secret')
        self.assertEqual(res.json['currency'], 'EUR')

    @patch('stripe.PaymentMethod.retrieve')
    @patch('stripe.PaymentIntent.create')
    def test_payment_intent_metadata_contains_order_id(self, mock_create, mock_retrieve):
        mock_retrieve.return_value = MagicMock()
        mock_create.return_value = _make_intent()

        self.login(self.user.username, '1')
        self.client.post(
            f'/api/v1/order/{self.order.id}/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )

        metadata = mock_create.call_args[1]['metadata']
        self.assertEqual(metadata['order_id'], self.order.id)

    @patch('stripe.PaymentMethod.retrieve')
    @patch('stripe.PaymentIntent.create')
    def test_payment_intent_metadata_contains_fee_fields(self, mock_create, mock_retrieve):
        mock_retrieve.return_value = MagicMock()
        mock_create.return_value = _make_intent()

        self.login(self.user.username, '1')
        self.client.post(
            f'/api/v1/order/{self.order.id}/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )

        metadata = mock_create.call_args[1]['metadata']
        self.assertIn('service_fee', metadata)
        self.assertIn('to_shipping_provider', metadata)
        # service_fee must be 2 % of shipping amount
        self.assertAlmostEqual(
            float(metadata['service_fee']),
            round(SHIPPING_EUR * 0.02, 2),
            places=2,
        )
        # to_shipping_provider must equal the raw shipping amount
        self.assertAlmostEqual(
            float(metadata['to_shipping_provider']),
            round(SHIPPING_EUR, 2),
            places=2,
        )

    @patch('stripe.PaymentMethod.retrieve')
    @patch('stripe.PaymentIntent.create')
    def test_payment_amount_uses_stripe_fee_structure(self, mock_create, mock_retrieve):
        from app.payments.routes.payment_methods.stripe import calculate_service_fee
        card_mock = MagicMock()
        card_mock.type = 'card'
        card_mock.card.country = 'DE'  # EEA country → domestic fee tier
        mock_retrieve.return_value = card_mock
        mock_create.return_value = _make_intent()

        self.login(self.user.username, '1')
        self.client.post(
            f'/api/v1/order/{self.order.id}/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )

        fees = calculate_service_fee(SHIPPING_EUR, 'DE', 'EUR')
        expected_cents = int(fees.send_to_stripe * 100)
        self.assertEqual(mock_create.call_args[1]['amount'], expected_cents)

    # ------------------------------------------------------------------
    # Validation / error cases
    # ------------------------------------------------------------------

    def test_returns_409_when_order_not_packed(self):
        order = Order(
            id='ORD-pay-api-np',
            user=self.user,
            country_id='c1',
            shipping=SeparateShipping.query.get(1),
            status=OrderStatus.pending,
            total_weight=500,
        )
        self.try_add_entity(order)

        self.login(self.user.username, '1')
        res = self.client.post(
            f'/api/v1/order/{order.id}/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )
        self.assertEqual(res.status_code, 409)

    def test_returns_409_when_shipping_method_not_separate(self):
        order = Order(
            id='ORD-pay-api-ns',
            user=self.user,
            country_id='c1',
            shipping=NoShipping.query.get(999),
            status=OrderStatus.packed,
            total_weight=500,
        )
        self.try_add_entity(order)

        self.login(self.user.username, '1')
        res = self.client.post(
            f'/api/v1/order/{order.id}/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )
        self.assertEqual(res.status_code, 409)

    def test_returns_400_when_payment_method_id_missing(self):
        self.login(self.user.username, '1')
        res = self.client.post(
            f'/api/v1/order/{self.order.id}/shipment/pay',
            json={},
        )
        self.assertEqual(res.status_code, 400)

    def test_returns_404_for_unknown_order(self):
        self.login(self.user.username, '1')
        res = self.client.post(
            '/api/v1/order/ORD-nonexistent/shipment/pay',
            json={'payment_method_id': 'pm_test'},
        )
        self.assertEqual(res.status_code, 404)


class TestShipmentPaymentClient(BaseTestCase):
    """Tests for GET /orders/<id>/shipment/pay and /shipment/pay/success"""

    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name='admin')
        self.user = User(
            username='user_test_shipment_client',
            email='user_shipment_client@test.com',
            password_hash=PW_HASH,
            enabled=True,
        )
        self.admin = User(
            username='admin_test_shipment_client',
            email='admin_shipment_client@test.com',
            password_hash=PW_HASH,
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=EUR_RATE),
            Country(id='c1', name='Country1'),
            SeparateShipping(id=1, name='Separate Shipping'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=SHIPPING_KRW),
        ])

        gen_id = f'ORD-pay-cl-{int(datetime.now().timestamp())}'
        self.order = Order(
            id=gen_id,
            user=self.user,
            country_id='c1',
            shipping=SeparateShipping.query.get(1),
            status=OrderStatus.packed,
            subtotal_krw=10000,
            shipping_krw=SHIPPING_KRW,
            shipping_cur2=SHIPPING_EUR,
            total_weight=500,
        )
        self.try_add_entity(self.order)

    # ------------------------------------------------------------------
    # Checkout page
    # ------------------------------------------------------------------

    def test_checkout_page_renders_for_packed_order(self):
        res = self.try_user_operation(
            lambda: self.client.get(f'/orders/{self.order.id}/shipment/pay')
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Pay Shipment', res.data)

    def test_checkout_page_returns_409_when_not_packed(self):
        order = Order(
            id='ORD-cl-np',
            user=self.user,
            country_id='c1',
            shipping=SeparateShipping.query.get(1),
            status=OrderStatus.pending,
            total_weight=500,
        )
        self.try_add_entity(order)

        self.login(self.user.username, '1')
        res = self.client.get(f'/orders/{order.id}/shipment/pay')
        self.assertEqual(res.status_code, 409)

    def test_checkout_page_unauthenticated_redirects(self):
        res = self.client.get(f'/orders/{self.order.id}/shipment/pay')
        self.assertEqual(res.status_code, 302)

    # ------------------------------------------------------------------
    # Success handler – happy path
    # ------------------------------------------------------------------

    @patch('stripe.PaymentIntent.retrieve')
    def test_success_handler_sets_shipment_is_paid_status(self, mock_retrieve):
        mock_retrieve.return_value = _make_intent(
            status='succeeded', order_id=self.order.id
        )

        self.login(self.user.username, '1')
        res = self.client.get(
            f'/orders/{self.order.id}/shipment/pay/success',
            query_string={'payment_intent': 'pi_test_123'},
        )
        self.assertEqual(res.status_code, 200)

        order = Order.query.get(self.order.id)
        self.assertEqual(order.status, OrderStatus.shipment_is_paid)

    @patch('stripe.PaymentIntent.retrieve')
    def test_success_page_shows_success_message(self, mock_retrieve):
        mock_retrieve.return_value = _make_intent(
            status='succeeded', order_id=self.order.id
        )

        self.login(self.user.username, '1')
        res = self.client.get(
            f'/orders/{self.order.id}/shipment/pay/success',
            query_string={'payment_intent': 'pi_test_123'},
        )
        self.assertIn(b'Payment Successful', res.data)

    # ------------------------------------------------------------------
    # Success handler – failure paths
    # ------------------------------------------------------------------

    @patch('stripe.PaymentIntent.retrieve')
    def test_failed_payment_does_not_change_order_status(self, mock_retrieve):
        mock_retrieve.return_value = _make_intent(
            status='requires_payment_method', order_id=self.order.id
        )

        self.login(self.user.username, '1')
        self.client.get(
            f'/orders/{self.order.id}/shipment/pay/success',
            query_string={'payment_intent': 'pi_test_123'},
        )

        order = Order.query.get(self.order.id)
        self.assertEqual(order.status, OrderStatus.packed)  # unchanged

    @patch('stripe.PaymentIntent.retrieve')
    def test_order_id_mismatch_does_not_change_status(self, mock_retrieve):
        mock_retrieve.return_value = _make_intent(
            status='succeeded', order_id='ORD-different-order'
        )

        self.login(self.user.username, '1')
        self.client.get(
            f'/orders/{self.order.id}/shipment/pay/success',
            query_string={'payment_intent': 'pi_test_123'},
        )

        order = Order.query.get(self.order.id)
        self.assertEqual(order.status, OrderStatus.packed)  # unchanged

    def test_missing_payment_intent_param_returns_failure_page(self):
        self.login(self.user.username, '1')
        res = self.client.get(f'/orders/{self.order.id}/shipment/pay/success')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Payment Failed', res.data)

    def test_success_handler_unauthenticated_redirects(self):
        res = self.client.get(
            f'/orders/{self.order.id}/shipment/pay/success',
            query_string={'payment_intent': 'pi_test_123'},
        )
        self.assertEqual(res.status_code, 302)
