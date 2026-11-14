"""Tests for EurocargoShipping method"""
import math
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import requests

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.models import Country
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.shipping.methods.eurocargo.models.eurocargo_shipping import EurocargoShipping
from app.shipping.models.shipping import NoShipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User
from app.shipping.models.shipping_rate import ShippingRate as _ShippingRate

PW_HASH = "pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576"


class TestEurocargoShippingModel(BaseTestCase):
    """Tests for EurocargoShipping cost-calculation behaviour"""

    def setUp(self):
        super().setUp()
        db.create_all()
        self.try_add_entities([
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=0.5),
            Country(id='c1', name='Country1'),
            EurocargoShipping(id=1, name='Eurocargo Shipping'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=5000),
        ])

    # ------------------------------------------------------------------
    # get_shipping_cost – must always return 0 at order-creation time
    # ------------------------------------------------------------------

    def test_get_shipping_cost_returns_zero_for_known_destination(self):
        shipping: EurocargoShipping = EurocargoShipping.query.get(1) #type: ignore
        self.assertEqual(shipping.get_shipping_cost('c1', 500), 0)

    def test_get_shipping_cost_returns_zero_for_unknown_destination(self):
        """Even when no rate is configured, cost is 0 (deferred to packing)"""
        shipping: EurocargoShipping = EurocargoShipping.query.get(1) #type: ignore
        self.assertEqual(shipping.get_shipping_cost('xx', 500), 0)

    # ------------------------------------------------------------------
    # can_ship – depends on ShippingRate entries (country availability list)
    # ------------------------------------------------------------------

    def test_can_ship_for_country_with_rate(self):
        """Country with a ShippingRate entry is available."""
        shipping = EurocargoShipping.query.get(1)
        country = Country.query.get('c1')
        self.assertTrue(shipping.can_ship(country, 500))

    def test_can_ship_for_country_without_rate(self):
        """Country without a ShippingRate entry is NOT available."""
        self.try_add_entity(Country(id='xx', name='No-Rate Country'))
        shipping = EurocargoShipping.query.get(1)
        country = Country.query.get('xx')
        self.assertFalse(shipping.can_ship(country, 500))

    # ------------------------------------------------------------------
    # polymorphic discriminator / to_dict
    # ------------------------------------------------------------------

    def test_discriminator_is_eurocargo(self):
        shipping = EurocargoShipping.query.get(1)
        self.assertEqual(shipping.discriminator, 'eurocargo')

    def test_to_dict_type_is_eurocargo(self):
        shipping = EurocargoShipping.query.get(1)
        self.assertEqual(shipping.to_dict()['type'], 'eurocargo')


class TestEurocargoShippingOrderIntegration(BaseTestCase):
    """Tests for Order.set_status() interaction with EurocargoShipping"""

    def setUp(self):
        super().setUp()
        db.create_all()
        # Explicitly connect the signal so tests are independent of app init order
        admin_role = Role(name='admin')
        self.actor = User(
            username='actor_test_eurocargo',
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
            EurocargoShipping(id=1, name='Eurocargo Shipping'),
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
        order = self._make_order(EurocargoShipping.query.get(1))
        order.set_status(OrderStatus.packed, self.actor)
        db.session.commit()

        self.assertEqual(order.status, OrderStatus.packed)
        self.assertEqual(order.shipping_base_currency, 0)  # untouched

    def test_set_status_packed_non_eurocargo_shipping_leaves_cost_unchanged(self):
        """Orders with NoShipping are not affected by the EurocargoShipping hook"""
        order = self._make_order(NoShipping.query.get(999), shipping_base_currency=100)
        order.set_status(OrderStatus.packed, self.actor)

        self.assertEqual(order.shipping_base_currency, 100)  # unchanged

    def test_set_status_packed_calls_eurocargo_api(self):
        """Setting a Eurocargo order to packed posts a shipment to the Eurocargo API."""
        from app.orders.models.order import OrderBox
        order = self._make_order(
            EurocargoShipping.query.get(1), status=OrderStatus.po_created,
            customer_name='Test Customer', email='customer@test.com',
            address='1 Test St', zip='10115')
        order.boxes = [OrderBox(length=30, width=20, height=10, weight=100, quantity=1)]
        db.session.commit()

        with patch('app.shipping.methods.eurocargo.signal_handlers.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                'token': 'tok123', 'shipment_url': 'http://example.com/shipments/tok123'}
            order.set_status(OrderStatus.packed, self.actor)

        self.assertEqual(order.status, OrderStatus.packed)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs['json']['order_id'], order.id)
        self.assertEqual(order.params['eurocargo.shipment_token.1'], 'tok123')

    def _make_shippable_order(self, shipping, status=OrderStatus.po_created, **kwargs):
        from app.orders.models.order import OrderBox
        fields = dict(customer_name='Test Customer', email='customer@test.com',
                      address='1 Test St', zip='10115')
        fields.update(kwargs)
        order = self._make_order(shipping, status=status, **fields)
        order.boxes = [OrderBox(length=30, width=20, height=10, weight=100, quantity=1)]
        db.session.commit()
        return order

    def _set_status_with_mocked_api(self, order, status):
        with patch('app.shipping.methods.eurocargo.signal_handlers.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                'token': 'tok123', 'shipment_url': 'http://example.com/shipments/tok123'}
            order.set_status(status, self.actor)
        return mock_post

    def test_set_status_packed_twice_posts_once(self):
        """Re-setting the same status must not create duplicate shipments."""
        order = self._make_shippable_order(EurocargoShipping.query.get(1))
        first = self._set_status_with_mocked_api(order, OrderStatus.packed)
        second = self._set_status_with_mocked_api(order, OrderStatus.packed)

        first.assert_called_once()
        second.assert_not_called()

    def test_set_status_packed_again_with_existing_shipment_no_api_call(self):
        """Going back to packed (e.g. from ready_to_ship) must not duplicate shipments."""
        order = self._make_shippable_order(EurocargoShipping.query.get(1))
        first = self._set_status_with_mocked_api(order, OrderStatus.packed)
        self._set_status_with_mocked_api(order, OrderStatus.ready_to_ship)
        again = self._set_status_with_mocked_api(order, OrderStatus.packed)

        first.assert_called_once()
        again.assert_not_called()

    def test_set_status_packed_legacy_shipment_url_no_api_call(self):
        """Orders whose shipment predates token storage are recognised by URL."""
        order = self._make_shippable_order(EurocargoShipping.query.get(1))
        order.params['eurocargo.shipment_url'] = 'http://example.com/shipments/old'
        mock_post = self._set_status_with_mocked_api(order, OrderStatus.packed)

        mock_post.assert_not_called()

    def test_set_status_packed_non_eurocargo_no_api_call(self):
        order = self._make_shippable_order(NoShipping.query.get(999))
        mock_post = self._set_status_with_mocked_api(order, OrderStatus.packed)

        self.assertEqual(order.status, OrderStatus.packed)
        mock_post.assert_not_called()

    def test_set_status_ready_to_ship_and_shipped_no_api_call(self):
        """Shipments are created on packed only."""
        order = self._make_shippable_order(EurocargoShipping.query.get(1),
                                           status=OrderStatus.packed)
        ready = self._set_status_with_mocked_api(order, OrderStatus.ready_to_ship)
        shipped = self._set_status_with_mocked_api(order, OrderStatus.shipped)

        self.assertEqual(order.status, OrderStatus.shipped)
        ready.assert_not_called()
        shipped.assert_not_called()

    def test_set_status_packed_api_error_keeps_status(self):
        order = self._make_shippable_order(EurocargoShipping.query.get(1))
        with patch('app.shipping.methods.eurocargo.signal_handlers.requests.post') as mock_post, \
                self.assertLogs('app.shipping.methods.eurocargo.signal_handlers',
                                level='ERROR') as logs:
            mock_post.return_value.raise_for_status.side_effect = \
                requests.HTTPError('500 Server Error')
            order.set_status(OrderStatus.packed, self.actor)

        self.assertEqual(order.status, OrderStatus.packed)
        mock_post.assert_called_once()
        self.assertNotIn('eurocargo.shipment_url', order.params or {})
        self.assertNotIn('eurocargo.shipment_token.1', order.params or {})
        self.assertIn('500 Server Error', logs.output[0])

    def test_set_status_packed_missing_fields_no_api_call(self):
        order = self._make_shippable_order(EurocargoShipping.query.get(1), email=None)
        with self.assertLogs('app.shipping.methods.eurocargo.signal_handlers',
                             level='ERROR') as logs:
            mock_post = self._set_status_with_mocked_api(order, OrderStatus.packed)

        self.assertEqual(order.status, OrderStatus.packed)
        mock_post.assert_not_called()
        self.assertIn('missing email', logs.output[0])

    # ------------------------------------------------------------------
    # Shipping method change → delete / re-create
    # ------------------------------------------------------------------

    def _with_shipment(self, order, tokens=('tok1', 'tok2')):
        for seq, token in enumerate(tokens, start=1):
            order.params[f'eurocargo.shipment_token.{seq}'] = token
        order.params['eurocargo.shipment_url'] = \
            f'http://example.com/shipments/{tokens[0]}'
        db.session.commit()
        return order

    def _set_shipping_with_mocked_api(self, order, shipping_id, status_code=204,
                                      side_effect=None):
        with patch('app.shipping.methods.eurocargo.signal_handlers.requests.delete') as mock_delete, \
             patch('app.shipping.methods.eurocargo.signal_handlers.requests.post') as mock_post:
            mock_delete.return_value.status_code = status_code
            if status_code >= 400:
                mock_delete.return_value.raise_for_status.side_effect = \
                    requests.HTTPError(f'{status_code} Error')
            if side_effect is not None:
                mock_delete.side_effect = side_effect
            mock_post.return_value.json.return_value = {
                'token': 'new', 'shipment_url': 'http://example.com/shipments/new'}
            order.set_shipping(shipping_id)
        return mock_delete, mock_post

    def _eurocargo_params(self, order):
        return {k: v for k, v in order.params.items() if k.startswith('eurocargo.')}

    def test_shipping_change_deletes_every_box_shipment(self):
        order = self._with_shipment(self._make_shippable_order(
            EurocargoShipping.query.get(1), status=OrderStatus.packed))
        mock_delete, mock_post = self._set_shipping_with_mocked_api(order, 999)

        self.assertEqual(order.shipping_method_id, 999)
        self.assertEqual(
            sorted(c.args[0].rsplit('/', 1)[-1] for c in mock_delete.call_args_list),
            ['tok1', 'tok2'])
        for c in mock_delete.call_args_list:
            self.assertIn('/api/v1/shipments/', c.args[0])
            self.assertNotIn('json', c.kwargs)
            self.assertNotIn('data', c.kwargs)
            self.assertIn('X-API-Key', c.kwargs['headers'])
        mock_post.assert_not_called()
        self.assertEqual(self._eurocargo_params(order), {})

    def test_shipping_change_delete_error_keeps_change_and_records_failure(self):
        order = self._with_shipment(self._make_shippable_order(
            EurocargoShipping.query.get(1), status=OrderStatus.packed), tokens=('tok1',))
        with self.assertLogs('app.shipping.methods.eurocargo.signal_handlers',
                             level='ERROR') as logs:
            self._set_shipping_with_mocked_api(order, 999, status_code=500)

        self.assertEqual(order.shipping_method_id, 999)
        self.assertEqual(self._eurocargo_params(order),
                         {'eurocargo.delete_failed.tok1': order.id})
        self.assertIn('500 Error', logs.output[0])

    def test_shipping_change_delete_network_error_records_failure(self):
        order = self._with_shipment(self._make_shippable_order(
            EurocargoShipping.query.get(1), status=OrderStatus.packed), tokens=('tok1',))
        with self.assertLogs('app.shipping.methods.eurocargo.signal_handlers',
                             level='ERROR'):
            self._set_shipping_with_mocked_api(
                order, 999, side_effect=requests.ConnectionError('down'))

        self.assertEqual(self._eurocargo_params(order),
                         {'eurocargo.delete_failed.tok1': order.id})

    def test_shipping_change_delete_404_treated_as_deleted(self):
        order = self._with_shipment(self._make_shippable_order(
            EurocargoShipping.query.get(1), status=OrderStatus.packed), tokens=('tok1',))
        self._set_shipping_with_mocked_api(order, 999, status_code=404)

        self.assertEqual(self._eurocargo_params(order), {})

    def test_shipping_change_deletes_legacy_shipment_by_url(self):
        order = self._make_shippable_order(EurocargoShipping.query.get(1),
                                           status=OrderStatus.packed)
        order.params['eurocargo.shipment_url'] = 'http://example.com/shipments/legacy'
        db.session.commit()
        mock_delete, _ = self._set_shipping_with_mocked_api(order, 999)

        mock_delete.assert_called_once()
        self.assertTrue(mock_delete.call_args.args[0].endswith('/api/v1/shipments/legacy'))
        self.assertEqual(self._eurocargo_params(order), {})

    def test_shipping_change_without_shipment_no_api_call(self):
        order = self._make_shippable_order(EurocargoShipping.query.get(1),
                                           status=OrderStatus.packed)
        mock_delete, mock_post = self._set_shipping_with_mocked_api(order, 999)

        mock_delete.assert_not_called()
        mock_post.assert_not_called()

    def test_shipping_change_to_eurocargo_when_packed_creates_shipment(self):
        order = self._make_shippable_order(NoShipping.query.get(999),
                                           status=OrderStatus.packed)
        mock_delete, mock_post = self._set_shipping_with_mocked_api(order, 1)

        mock_delete.assert_not_called()
        mock_post.assert_called_once()
        self.assertEqual(order.params['eurocargo.shipment_token.1'], 'new')

    def test_shipping_change_to_eurocargo_before_packed_no_shipment(self):
        order = self._make_shippable_order(NoShipping.query.get(999),
                                           status=OrderStatus.po_created)
        _, mock_post = self._set_shipping_with_mocked_api(order, 1)

        mock_post.assert_not_called()

    def test_shipping_change_to_eurocargo_with_existing_shipment_keeps_it(self):
        """E.g. shipment created by `flask eurocargo ship-invoice` for a non-Eurocargo order."""
        order = self._with_shipment(self._make_shippable_order(
            NoShipping.query.get(999), status=OrderStatus.packed), tokens=('tok1',))
        mock_delete, mock_post = self._set_shipping_with_mocked_api(order, 1)

        mock_delete.assert_not_called()
        mock_post.assert_not_called()
        self.assertEqual(order.params['eurocargo.shipment_token.1'], 'tok1')

    def test_shipment_is_paid_status_exists_in_enum(self):
        self.assertIn('shipment_is_paid', [s.name for s in OrderStatus])
        self.assertEqual(OrderStatus.shipment_is_paid.value, 9)


class _ShippedHandlerMixin:
    """Shared helpers for on_sale_order_shipped tests."""

    def _make_order(self, boxes=None, total_weight=2000, order_products=None):
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
        order.invoice_id = None
        order.invoice = None
        order.order_products = order_products or []
        shipping = MagicMock()
        order.shipping = shipping
        return order

    def _make_box(self, length, width, height, quantity=1):
        box = MagicMock()
        box.length = length
        box.width = width
        box.height = height
        box.quantity = quantity
        return box

    def _call_handler(self, order, eur_rate=0.001):
        from app.shipping.methods.eurocargo.signal_handlers import on_sale_order_packed
        from app.shipping.methods.eurocargo.models.eurocargo_shipping import EurocargoShipping
        order.shipping.__class__ = EurocargoShipping
        order.shipping.id = 1
        with patch('app.shipping.methods.eurocargo.signal_handlers.requests.post') as mock_post, \
             patch('app.shipping.methods.eurocargo.signal_handlers._eur_rate',
                   return_value=eur_rate):
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                'token': 'tok123', 'shipment_url': 'http://example.com/shipments/tok123'
            }
            mock_post.return_value.raise_for_status = MagicMock()
            on_sale_order_packed(order)
            return mock_post

    def _all_payloads(self, mock_post):
        return [c[1]['json'] for c in mock_post.call_args_list]

    def _post(self, order, **kwargs):
        """Convenience: call handler and return mock_post."""
        return self._call_handler(order, **kwargs)

    def _make_op(self, product_id='P1', price=10000, quantity=1, weight=250,
                 name_english='Shampoo', name='샴푸', status=None):
        from app.orders.models.order_product import OrderProductStatus
        op = MagicMock()
        op.product_id = product_id
        op.price = price
        op.quantity = quantity
        op.status = status or OrderProductStatus.purchased
        op.product.name_english = name_english
        op.product.name = name
        op.product.weight = weight
        return op


class TestOnSaleOrderShippedSignalHandler(_ShippedHandlerMixin, BaseTestCase):
    """Unit tests for the on_sale_order_shipped signal handler (eurocargo creation)."""

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

    def test_no_boxes_no_shipment_created(self):
        """Eurocargo rejects API shipments without dimensions, so don't post."""
        order = self._make_order(boxes=[], total_weight=1000)
        mock_post = self._post(order)
        mock_post.assert_not_called()

    def test_box_without_dimensions_no_shipment_created(self):
        order = self._make_order(boxes=[self._make_box(None, 30, 20)], total_weight=1000)
        mock_post = self._post(order)
        mock_post.assert_not_called()

    # ------------------------------------------------------------------
    # Multi-box
    # ------------------------------------------------------------------

    def test_two_distinct_boxes_creates_two_shipments(self):
        boxes = [self._make_box(40, 30, 20), self._make_box(50, 40, 30)]
        order = self._make_order(boxes=boxes, total_weight=4000)
        mock_post = self._post(order)
        self.assertEqual(mock_post.call_count, 2)

    def test_two_boxes_store_token_per_box(self):
        boxes = [self._make_box(40, 30, 20), self._make_box(50, 40, 30)]
        order = self._make_order(boxes=boxes, total_weight=4000)
        self._post(order)
        self.assertEqual(order.params['eurocargo.shipment_token.1'], 'tok123')
        self.assertEqual(order.params['eurocargo.shipment_token.2'], 'tok123')
        self.assertEqual(order.params['eurocargo.shipment_url'],
                         'http://example.com/shipments/tok123')

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

    # ------------------------------------------------------------------
    # additional_cost_eur: first leg is priced by Eurocargo itself
    # ------------------------------------------------------------------

    def test_additional_cost_eur_never_sent(self):
        order = self._make_order(boxes=[self._make_box(40, 30, 20)], total_weight=2000)
        payload = self._post(order).call_args[1]['json']
        self.assertNotIn('additional_cost_eur', payload)

    def test_non_eurocargo_shipping_skipped(self):
        order = self._make_order()
        from app.shipping.methods.eurocargo.signal_handlers import on_sale_order_packed
        with patch('app.shipping.methods.eurocargo.signal_handlers.requests.post') as mock_post:
            on_sale_order_packed(order)  # shipping.__class__ is MagicMock, not EurocargoShipping
            mock_post.assert_not_called()

    def test_shipment_payload_does_not_include_carrier(self):
        """Carrier is chosen by customer at payment time; must not be sent at creation."""
        box = self._make_box(40, 30, 20)
        order = self._make_order(boxes=[box], total_weight=1000)
        mock_post = self._post(order)
        payload = mock_post.call_args[1]['json']
        self.assertNotIn('shipment_type_code', payload)


class TestEurocargoShipmentPayload(_ShippedHandlerMixin, BaseTestCase):
    """Payload fields matching the Eurocargo ShipmentCreate schema."""

    def _single(self, **kwargs):
        return self._make_order(boxes=[self._make_box(40, 30, 20)], total_weight=1000,
                                **kwargs)

    def _payload(self, order, **kwargs):
        return self._post(order, **kwargs).call_args[1]['json']

    # container_id

    def test_container_id_from_invoice(self):
        order = self._single()
        order.invoice_id = 'INV-2026-11-0001'
        self.assertEqual(self._payload(order)['container_id'], 'CNT-INV-2026-11-0001')

    def test_container_id_prefers_invoice_export_id(self):
        order = self._single()
        order.invoice_id = 'INV-2026-11-0001'
        order.invoice = MagicMock(export_id='EXP-42')
        self.assertEqual(self._payload(order)['container_id'], 'CNT-EXP-42')

    def test_container_id_falls_back_to_invoice_id_without_export_id(self):
        order = self._single()
        order.invoice_id = 'INV-2026-11-0001'
        order.invoice = MagicMock(export_id=None)
        self.assertEqual(self._payload(order)['container_id'], 'CNT-INV-2026-11-0001')

    def test_container_id_falls_back_to_order_id(self):
        self.assertEqual(self._payload(self._single())['container_id'], 'CNT-ORD-TEST-001')

    def test_container_id_same_on_every_box(self):
        order = self._make_order(boxes=[self._make_box(10, 10, 10, quantity=2)],
                                 total_weight=2000)
        ids = {p['container_id'] for p in self._all_payloads(self._post(order))}
        self.assertEqual(ids, {'CNT-ORD-TEST-001'})

    # items

    def test_items_mapped(self):
        order = self._single(order_products=[
            self._make_op(price=12345, quantity=2, weight=250)])
        items = self._payload(order, eur_rate=0.001)['items']
        self.assertEqual(items, [{
            'name': 'Shampoo', 'weight_kg': '0.250', 'price_eur': '12.35', 'quantity': 2,
        }])

    def test_unavailable_products_excluded(self):
        from app.orders.models.order_product import OrderProductStatus
        order = self._single(order_products=[
            self._make_op(product_id='P1'),
            self._make_op(product_id='P2', status=OrderProductStatus.unavailable),
        ])
        items = self._payload(order)['items']
        self.assertEqual(len(items), 1)

    def test_same_product_and_price_merged(self):
        order = self._single(order_products=[
            self._make_op(quantity=1), self._make_op(quantity=3)])
        items = self._payload(order)['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['quantity'], 4)

    def test_same_product_different_price_not_merged(self):
        order = self._single(order_products=[
            self._make_op(price=10000), self._make_op(price=9000)])
        self.assertEqual(len(self._payload(order)['items']), 2)

    def test_item_name_falls_back_to_korean_then_id(self):
        order = self._single(order_products=[
            self._make_op(product_id='P1', name_english=None, name='샴푸'),
            self._make_op(product_id='P2', name_english='', name=None),
        ])
        names = [i['name'] for i in self._payload(order)['items']]
        self.assertEqual(names, ['샴푸', 'P2'])

    def test_item_without_weight_sends_zero(self):
        order = self._single(order_products=[self._make_op(weight=None)])
        self.assertEqual(self._payload(order)['items'][0]['weight_kg'], '0.000')

    def test_items_over_limit_folded_into_other_items(self):
        ops = [self._make_op(product_id=f'P{i}', price=1000, weight=100)
               for i in range(105)]
        items = self._payload(self._single(order_products=ops), eur_rate=0.001)['items']
        self.assertEqual(len(items), 100)
        self.assertEqual(items[-1]['name'], 'Other items')
        self.assertEqual(items[-1]['quantity'], 1)
        self.assertEqual(items[-1]['price_eur'], '6.00')   # 6 lines × 1.00
        self.assertEqual(items[-1]['weight_kg'], '0.600')

    def test_no_items_when_eur_rate_unknown(self):
        order = self._single(order_products=[self._make_op()])
        payload = self._payload(order, eur_rate=None)
        self.assertNotIn('items', payload)
        order = self._single(order_products=[self._make_op()])
        self.assertEqual(self._post(order, eur_rate=None).call_count, 1)

    def test_no_items_key_when_order_has_no_products(self):
        self.assertNotIn('items', self._payload(self._single()))

    def test_declared_cost_left_to_eurocargo_on_single_box(self):
        order = self._single(order_products=[self._make_op()])
        self.assertNotIn('declared_cost_eur', self._payload(order))

    def test_multi_box_items_only_on_first_box(self):
        order = self._make_order(boxes=[self._make_box(10, 10, 10, quantity=3)],
                                 total_weight=3000, order_products=[self._make_op()])
        payloads = self._all_payloads(self._post(order))
        self.assertEqual(len(payloads[0]['items']), 1)
        self.assertNotIn('declared_cost_eur', payloads[0])
        for payload in payloads[1:]:
            self.assertNotIn('items', payload)
            self.assertEqual(payload['declared_cost_eur'], '0')

    def test_description_not_sent(self):
        self.assertNotIn('description', self._payload(self._single()))

    def test_multi_box_first_box_has_no_description(self):
        order = self._make_order(boxes=[self._make_box(10, 10, 10, quantity=3)],
                                 total_weight=3000, order_products=[self._make_op()])
        self.assertNotIn('description', self._all_payloads(self._post(order))[0])

    def test_multi_box_other_boxes_point_to_first(self):
        order = self._make_order(boxes=[self._make_box(10, 10, 10, quantity=3)],
                                 total_weight=3000, order_products=[self._make_op()])
        payloads = self._all_payloads(self._post(order))
        self.assertEqual(
            [p['description'] for p in payloads[1:]],
            ['Part 2 of 3 of order ORD-TEST-001, contents declared on ORD-TEST-001-1',
             'Part 3 of 3 of order ORD-TEST-001, contents declared on ORD-TEST-001-1'])

    # recipient sanitising

    def test_address_line_breaks_flattened(self):
        order = self._single()
        order.address = 'Hauptstr. 12\r\nHinterhaus\n\tApt 3 '
        self.assertEqual(self._payload(order)['address'], 'Hauptstr. 12, Hinterhaus, Apt 3')

    def test_empty_phone_sent_as_none(self):
        order = self._single()
        order.phone = ''
        self.assertIsNone(self._payload(order)['phone'])

    def test_missing_email_no_shipment_created(self):
        order = self._single()
        order.email = None
        self._post(order).assert_not_called()

    def test_missing_address_no_shipment_created(self):
        order = self._single()
        order.address = ' \n '
        self._post(order).assert_not_called()


class TestEurocargoShippingAdminAPI(BaseTestCase):
    """Tests for the admin API endpoints managing country availability."""

    PW = 'pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576'

    def setUp(self):
        super().setUp()
        db.create_all()
        admin_role = Role(name='admin')
        self.admin = User(
            username='admin_eurocargo_api',
            email='admin_eurocargo_api@test.com',
            password_hash=self.PW,
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities([
            admin_role, self.admin,
            Country(id='DE', name='Germany'),
            Country(id='FR', name='France'),
            Country(id='PL', name='Poland'),
            EurocargoShipping(id=10, name='Sep Ship'),
            # DE is pre-enabled
            _ShippingRate(shipping_method_id=10, destination='DE', weight=0, rate=0),
        ])
        self.login('admin_eurocargo_api', '1')

    # ------------------------------------------------------------------
    # GET /<id>/countries
    # ------------------------------------------------------------------

    def test_get_countries_returns_configured_list(self):
        res = self.client.get('/api/v1/admin/shipping/eurocargo/10/countries')
        self.assertEqual(res.status_code, 200)
        self.assertIn('DE', res.json)

    def test_get_countries_excludes_unconfigured(self):
        res = self.client.get('/api/v1/admin/shipping/eurocargo/10/countries')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('FR', res.json)

    def test_get_countries_not_found(self):
        res = self.client.get('/api/v1/admin/shipping/eurocargo/999/countries')
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------------------------
    # POST /<id>/countries
    # ------------------------------------------------------------------

    def test_save_countries_adds_new(self):
        res = self.client.post(
            '/api/v1/admin/shipping/eurocargo/10/countries',
            json={'countries': ['DE', 'FR']},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('FR', res.json)
        # Verify can_ship now returns True for FR
        from app.shipping.methods.eurocargo.models.eurocargo_shipping import EurocargoShipping as SS
        shipping = db.session.get(SS, 10)
        db.session.expire_all()
        fr = Country.query.get('FR')
        self.assertTrue(shipping.can_ship(fr, 0))

    def test_save_countries_removes_deselected(self):
        res = self.client.post(
            '/api/v1/admin/shipping/eurocargo/10/countries',
            json={'countries': ['FR']},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        # DE was pre-enabled but not in new list → removed
        from app.shipping.methods.eurocargo.models.eurocargo_shipping import EurocargoShipping as SS
        shipping = db.session.get(SS, 10)
        db.session.expire_all()
        de = Country.query.get('DE')
        self.assertFalse(shipping.can_ship(de, 0))

    def test_save_countries_empty_list_clears_all(self):
        res = self.client.post(
            '/api/v1/admin/shipping/eurocargo/10/countries',
            json={'countries': []},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        from app.shipping.methods.eurocargo.models.eurocargo_shipping import EurocargoShipping as SS
        shipping = db.session.get(SS, 10)
        db.session.expire_all()
        de = Country.query.get('DE')
        self.assertFalse(shipping.can_ship(de, 0))

    def test_save_countries_unknown_code_rejected(self):
        res = self.client.post(
            '/api/v1/admin/shipping/eurocargo/10/countries',
            json={'countries': ['XX']},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 422)

    def test_save_countries_not_found(self):
        res = self.client.post(
            '/api/v1/admin/shipping/eurocargo/999/countries',
            json={'countries': ['DE']},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 404)

    def test_save_countries_requires_admin(self):
        self.logout()
        res = self.client.post(
            '/api/v1/admin/shipping/eurocargo/10/countries',
            json={'countries': ['DE']},
            content_type='application/json',
        )
        self.assertIn(res.status_code, [401, 403])

    # ------------------------------------------------------------------
    # /<id>/settings removed: Eurocargo prices the first leg itself
    # ------------------------------------------------------------------

    def test_settings_endpoint_removed(self):
        self.assertEqual(
            self.client.get('/api/v1/admin/shipping/eurocargo/10/settings').status_code, 404)
        self.assertIn(self.client.post(
            '/api/v1/admin/shipping/eurocargo/10/settings',
            json={'first_leg': '1.5'}).status_code, [404, 405])
