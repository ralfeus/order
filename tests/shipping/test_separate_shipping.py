"""Tests for SeparateShipping method"""
import math
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.models import Country
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.shipping.methods.separate.models.separate_shipping import SeparateShipping
from app.shipping.models.shipping import NoShipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User
from common.exceptions import NoShippingRateError

PW_HASH = "pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576"


class TestSeparateShippingModel(BaseTestCase):
    """Tests for SeparateShipping cost-calculation behaviour"""

    def setUp(self):
        super().setUp()
        db.create_all()
        self.try_add_entities([
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=0.5),
            Country(id='c1', name='Country1'),
            SeparateShipping(id=1, name='Separate Shipping'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=5000),
        ])

    # ------------------------------------------------------------------
    # get_shipping_cost – must always return 0 at order-creation time
    # ------------------------------------------------------------------

    def test_get_shipping_cost_returns_zero_for_known_destination(self):
        shipping: SeparateShipping = SeparateShipping.query.get(1) #type: ignore
        self.assertEqual(shipping.get_shipping_cost('c1', 500), 0)

    def test_get_shipping_cost_returns_zero_for_unknown_destination(self):
        """Even when no rate is configured, cost is 0 (deferred to packing)"""
        shipping: SeparateShipping = SeparateShipping.query.get(1) #type: ignore
        self.assertEqual(shipping.get_shipping_cost('xx', 500), 0)

    # ------------------------------------------------------------------
    # get_actual_shipping_cost – standard rate-table lookup
    # ------------------------------------------------------------------

    def test_get_actual_shipping_cost_returns_configured_rate(self):
        shipping: SeparateShipping = SeparateShipping.query.get(1) #type: ignore
        cost = shipping.get_actual_shipping_cost('c1', 500)
        self.assertEqual(cost, 5000)

    def test_get_actual_shipping_cost_no_rate_raises_error(self):
        shipping: SeparateShipping = SeparateShipping.query.get(1) #type: ignore
        with self.assertRaises(NoShippingRateError):
            shipping.get_actual_shipping_cost('xx', 500)

    # ------------------------------------------------------------------
    # can_ship – always True (real rate check is deferred to packing)
    # ------------------------------------------------------------------

    def test_can_ship_for_country_with_rate(self):
        shipping = SeparateShipping.query.get(1)
        country = Country.query.get('c1')
        self.assertTrue(shipping.can_ship(country, 500))

    def test_can_ship_for_country_without_rate(self):
        """SeparateShipping.can_ship() always True regardless of rate presence"""
        self.try_add_entity(Country(id='xx', name='No-Rate Country'))
        shipping = SeparateShipping.query.get(1)
        country = Country.query.get('xx')
        self.assertTrue(shipping.can_ship(country, 500))

    # ------------------------------------------------------------------
    # polymorphic discriminator / to_dict
    # ------------------------------------------------------------------

    def test_discriminator_is_separate(self):
        shipping = SeparateShipping.query.get(1)
        self.assertEqual(shipping.discriminator, 'separate')

    def test_to_dict_type_is_separate(self):
        shipping = SeparateShipping.query.get(1)
        self.assertEqual(shipping.to_dict()['type'], 'separate')


class TestSeparateShippingOrderIntegration(BaseTestCase):
    """Tests for Order.set_status() interaction with SeparateShipping"""

    def setUp(self):
        super().setUp()
        db.create_all()
        # Explicitly connect the signal so tests are independent of app init order
        admin_role = Role(name='admin')
        self.actor = User(
            username='actor_test_separate',
            email='actor@test.com',
            password_hash=PW_HASH,
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities([
            self.actor, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=0.5),
            Country(id='c1', name='Country1'),
            SeparateShipping(id=1, name='Separate Shipping'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=5000),
            NoShipping(id=999),
        ])

    def _make_order(self, shipping, status=OrderStatus.po_created, **kwargs):
        kwargs.setdefault('shipping_base_currency', 0)
        order = Order(
            user=self.actor,
            country_id='c1',
            shipping=shipping,
            subtotal_base_currency=10000,
            total_weight=500,
            shipping_box_weight=0,
            status=status,
            **kwargs,
        )
        self.try_add_entity(order)
        return order

    def test_set_status_packed_does_not_calculate_shipping_cost(self):
        """Cost calculation moved to shipped; packing must not touch shipping_base_currency."""
        order = self._make_order(SeparateShipping.query.get(1))
        order.set_status(OrderStatus.packed, self.actor)
        db.session.commit()

        self.assertEqual(order.status, OrderStatus.packed)
        self.assertEqual(order.shipping_base_currency, 0)  # untouched

    def test_set_status_packed_non_separate_shipping_leaves_cost_unchanged(self):
        """Orders with NoShipping are not affected by the SeparateShipping hook"""
        order = self._make_order(NoShipping.query.get(999), shipping_base_currency=100)
        order.set_status(OrderStatus.packed, self.actor)

        self.assertEqual(order.shipping_base_currency, 100)  # unchanged

    def test_shipment_is_paid_status_exists_in_enum(self):
        self.assertIn('shipment_is_paid', [s.name for s in OrderStatus])
        self.assertEqual(OrderStatus.shipment_is_paid.value, 9)


class TestOnSaleOrderPackedSignalHandler(BaseTestCase):
    """on_sale_order_packed is a no-op for SeparateShipping (cost deferred to shipped)."""

    def test_packed_handler_does_nothing(self):
        order = MagicMock()
        from app.shipping.methods.separate.signal_handlers import on_sale_order_packed
        on_sale_order_packed(order)
        # No attributes should have been set
        order.assert_not_called()


class _ShippedHandlerMixin:
    """Shared helpers for on_sale_order_shipped tests."""

    def _make_order(self, boxes=None, total_weight=2000):
        order = MagicMock()
        order.id = 'ORD-TEST-001'
        order.customer_name = 'Test Customer'
        order.email = 'test@example.com'
        order.address = '1 Test St'
        order.city_eng = 'Berlin'
        order.country_id = 'DE'
        order.zip = '10115'
        order.phone = '+4912345'
        order.tracking_id = None
        order.total_weight = total_weight  # grams
        order.shipping_box_weight = 0
        order.boxes = boxes or []
        order.params = {}
        # Numeric fields needed for cost-update arithmetic
        order.subtotal_base_currency = 0
        order.subtotal_user_currency = 0
        order.service_fee = 0
        order.shipping_base_currency = 0
        order.shipping_user_currency = 0
        order.total_base_currency = 0
        order.total_user_currency = 0
        order.user_currency_code = None
        shipping = MagicMock()
        shipping.subtype_code = 'GLS'
        order.shipping = shipping
        return order

    def _make_box(self, length, width, height, quantity=1):
        box = MagicMock()
        box.length = length
        box.width = width
        box.height = height
        box.quantity = quantity
        return box

    def _call_handler(self, order, cost_eur=100.0):
        from app.shipping.methods.separate.signal_handlers import on_sale_order_shipped
        from app.shipping.methods.separate.models.separate_shipping import SeparateShipping
        order.shipping.__class__ = SeparateShipping
        with patch('app.shipping.methods.separate.signal_handlers.requests.get') as mock_get, \
             patch('app.shipping.methods.separate.signal_handlers.requests.post') as mock_post:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'cost_eur': str(cost_eur)}
            mock_get.return_value.raise_for_status = MagicMock()
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                'token': 'tok123', 'shipment_url': 'http://example.com/shipments/tok123'
            }
            mock_post.return_value.raise_for_status = MagicMock()
            on_sale_order_shipped(order)
            return mock_get, mock_post

    def _all_payloads(self, mock_post):
        return [c[1]['json'] for c in mock_post.call_args_list]

    def _post(self, order, **kw):
        """Convenience: call handler and return only mock_post."""
        _, mock_post = self._call_handler(order, **kw)
        return mock_post


class TestOnSaleOrderShippedSignalHandler(_ShippedHandlerMixin, BaseTestCase):
    """Unit tests for the on_sale_order_shipped signal handler (eurocargo creation)."""

    # ------------------------------------------------------------------
    # Cost fetch via ECmgmt
    # ------------------------------------------------------------------

    def test_shipping_cost_set_on_order(self):
        order = self._make_order()
        self._call_handler(order, cost_eur=250.0)
        self.assertAlmostEqual(float(order.shipping_base_currency), 250.0)

    def test_total_base_currency_updated(self):
        order = self._make_order()
        order.subtotal_base_currency = 1000
        order.service_fee = 50
        self._call_handler(order, cost_eur=200.0)
        self.assertAlmostEqual(float(order.total_base_currency), 1250.0)

    def test_cost_endpoint_receives_correct_weight(self):
        # total_weight=2000 g + shipping_box_weight=0 → 2.0 kg
        order = self._make_order(total_weight=2000)
        mock_get, _ = self._call_handler(order)
        params = mock_get.call_args[1]['params']
        self.assertAlmostEqual(float(params['weight_kg']), 2.0)

    def test_single_box_dimensions_sent_to_cost_endpoint(self):
        box = self._make_box(40, 30, 20)
        order = self._make_order(boxes=[box], total_weight=1000)
        mock_get, _ = self._call_handler(order)
        params = mock_get.call_args[1]['params']
        self.assertEqual(params['length_cm'], '40')
        self.assertEqual(params['width_cm'], '30')
        self.assertEqual(params['height_cm'], '20')

    def test_multi_box_no_dimensions_in_cost_endpoint(self):
        boxes = [self._make_box(40, 30, 20), self._make_box(50, 40, 30)]
        order = self._make_order(boxes=boxes, total_weight=4000)
        mock_get, _ = self._call_handler(order)
        params = mock_get.call_args[1]['params']
        self.assertNotIn('length_cm', params)

    def test_aborts_when_cost_fetch_fails(self):
        order = self._make_order()
        from app.shipping.methods.separate.signal_handlers import on_sale_order_shipped
        from app.shipping.methods.separate.models.separate_shipping import SeparateShipping
        order.shipping.__class__ = SeparateShipping
        with patch('app.shipping.methods.separate.signal_handlers.requests.get') as mock_get, \
             patch('app.shipping.methods.separate.signal_handlers.requests.post') as mock_post:
            mock_get.return_value.raise_for_status.side_effect = Exception('no rate')
            on_sale_order_shipped(order)
            mock_post.assert_not_called()

    # ------------------------------------------------------------------
    # Single box (qty=1)
    # ------------------------------------------------------------------

    def test_single_box_one_shipment_created(self):
        box = self._make_box(40, 30, 20)
        order = self._make_order(boxes=[box], total_weight=1000)
        mock_post = self._post(order)
        self.assertEqual(mock_post.call_count, 1)

    def test_single_box_uses_original_order_id(self):
        box = self._make_box(40, 30, 20)
        order = self._make_order(boxes=[box], total_weight=1000)
        mock_post = self._post(order)
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['order_id'], 'ORD-TEST-001')

    def test_single_box_dimensions_passed(self):
        box = self._make_box(40, 30, 20)
        order = self._make_order(boxes=[box], total_weight=1000)
        mock_post = self._post(order)
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['length_cm'], 40)
        self.assertEqual(payload['width_cm'], 30)
        self.assertEqual(payload['height_cm'], 20)

    def test_no_boxes_one_shipment_created(self):
        order = self._make_order(boxes=[], total_weight=1000)
        mock_post = self._post(order)
        self.assertEqual(mock_post.call_count, 1)
        payload = mock_post.call_args[1]['json']
        self.assertNotIn('length_cm', payload)

    # ------------------------------------------------------------------
    # Multi-box
    # ------------------------------------------------------------------

    def test_two_distinct_boxes_creates_two_shipments(self):
        boxes = [self._make_box(40, 30, 20), self._make_box(50, 40, 30)]
        order = self._make_order(boxes=boxes, total_weight=4000)
        mock_post = self._post(order)
        self.assertEqual(mock_post.call_count, 2)

    def test_two_distinct_boxes_order_ids_suffixed(self):
        boxes = [self._make_box(40, 30, 20), self._make_box(50, 40, 30)]
        order = self._make_order(boxes=boxes, total_weight=4000)
        mock_post = self._post(order)
        order_ids = [p['order_id'] for p in self._all_payloads(mock_post)]
        self.assertEqual(order_ids, ['ORD-TEST-001-1', 'ORD-TEST-001-2'])

    def test_two_distinct_boxes_each_has_own_dimensions(self):
        box1 = self._make_box(40, 30, 20)
        box2 = self._make_box(50, 40, 30)
        order = self._make_order(boxes=[box1, box2], total_weight=4000)
        mock_post = self._post(order)
        payloads = self._all_payloads(mock_post)
        self.assertEqual(payloads[0]['length_cm'], 40)
        self.assertEqual(payloads[1]['length_cm'], 50)

    def test_single_box_qty2_creates_two_shipments(self):
        box = self._make_box(40, 30, 20, quantity=2)
        order = self._make_order(boxes=[box], total_weight=4000)
        mock_post = self._post(order)
        self.assertEqual(mock_post.call_count, 2)

    def test_single_box_qty2_order_ids_suffixed(self):
        box = self._make_box(40, 30, 20, quantity=2)
        order = self._make_order(boxes=[box], total_weight=4000)
        mock_post = self._post(order)
        order_ids = [p['order_id'] for p in self._all_payloads(mock_post)]
        self.assertEqual(order_ids, ['ORD-TEST-001-1', 'ORD-TEST-001-2'])

    def test_mixed_qty_seq_is_global(self):
        box1 = self._make_box(40, 30, 20, quantity=2)
        box2 = self._make_box(50, 40, 30, quantity=1)
        order = self._make_order(boxes=[box1, box2], total_weight=6000)
        mock_post = self._post(order)
        self.assertEqual(mock_post.call_count, 3)
        order_ids = [p['order_id'] for p in self._all_payloads(mock_post)]
        self.assertEqual(order_ids, ['ORD-TEST-001-1', 'ORD-TEST-001-2', 'ORD-TEST-001-3'])

    def test_multi_box_first_url_stored(self):
        boxes = [self._make_box(40, 30, 20), self._make_box(50, 40, 30)]
        order = self._make_order(boxes=boxes, total_weight=4000)
        self._call_handler(order)
        self.assertIn('eurocargo.shipment_url', order.params)

    # ------------------------------------------------------------------
    # Volumetric vs. actual weight (single box)
    # ------------------------------------------------------------------

    def test_single_box_volumetric_heavier_than_actual(self):
        # 50×40×30 → 12.0 kg volumetric; actual 1 kg → billable 12 kg
        box = self._make_box(50, 40, 30)
        order = self._make_order(boxes=[box], total_weight=1000)
        mock_post = self._post(order)
        payload = mock_post.call_args[1]['json']
        self.assertAlmostEqual(float(payload['weight_kg']), 12.0)

    def test_single_box_actual_heavier_than_volumetric(self):
        # 10×10×10 → 0.2 kg volumetric; actual 5 kg → billable 5 kg
        box = self._make_box(10, 10, 10)
        order = self._make_order(boxes=[box], total_weight=5000)
        mock_post = self._post(order)
        payload = mock_post.call_args[1]['json']
        self.assertAlmostEqual(float(payload['weight_kg']), 5.0)

    # ------------------------------------------------------------------
    # Volumetric vs. actual weight (multi-box)
    # ------------------------------------------------------------------

    def test_multi_box_weight_distributed_evenly(self):
        box1 = self._make_box(10, 10, 10)
        box2 = self._make_box(10, 10, 10)
        order = self._make_order(boxes=[box1, box2], total_weight=4000)
        mock_post = self._post(order)
        for payload in self._all_payloads(mock_post):
            self.assertAlmostEqual(float(payload['weight_kg']), 2.0)

    def test_multi_box_volumetric_wins_per_unit(self):
        box1 = self._make_box(50, 40, 30)
        box2 = self._make_box(50, 40, 30)
        order = self._make_order(boxes=[box1, box2], total_weight=1000)
        mock_post = self._post(order)
        for payload in self._all_payloads(mock_post):
            self.assertAlmostEqual(float(payload['weight_kg']), 12.0)

    def test_multi_box_different_sizes_different_weights(self):
        box1 = self._make_box(10, 10, 10)
        box2 = self._make_box(50, 40, 30)
        order = self._make_order(boxes=[box1, box2], total_weight=1000)
        mock_post = self._post(order)
        payloads = self._all_payloads(mock_post)
        self.assertAlmostEqual(float(payloads[0]['weight_kg']), 0.5)
        self.assertAlmostEqual(float(payloads[1]['weight_kg']), 12.0)

    def test_non_separate_shipping_skipped(self):
        order = self._make_order()
        from app.shipping.methods.separate.signal_handlers import on_sale_order_shipped
        with patch('app.shipping.methods.separate.signal_handlers.requests.get') as mock_get, \
             patch('app.shipping.methods.separate.signal_handlers.requests.post') as mock_post:
            on_sale_order_shipped(order)  # shipping.__class__ is MagicMock, not SeparateShipping
            mock_get.assert_not_called()
            mock_post.assert_not_called()
