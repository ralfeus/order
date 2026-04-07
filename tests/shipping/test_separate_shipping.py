"""Tests for SeparateShipping method"""
import math

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
        from app.orders.signals import sale_order_packed
        from app.shipping.methods.separate.signal_handlers import on_sale_order_packed
        sale_order_packed.connect(on_sale_order_packed)
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

    def test_set_status_packed_calculates_shipping_base_currency(self):
        order = self._make_order(SeparateShipping.query.get(1))
        order.set_status(OrderStatus.packed, self.actor)
        db.session.commit()

        self.assertEqual(order.status, OrderStatus.packed)
        self.assertEqual(order.shipping_base_currency, 5000)

    def test_set_status_packed_updates_user_currency_amount(self):
        """EUR rate = 0.5, so 5000 KRW * 0.5 = 2500 stored in shipping_user_currency"""
        order = self._make_order(SeparateShipping.query.get(1),
                                 user_currency_code='EUR')
        order.set_status(OrderStatus.packed, self.actor)
        db.session.commit()

        self.assertAlmostEqual(float(order.shipping_user_currency), 2500.0)

    def test_set_status_packed_updates_total(self):
        order = self._make_order(SeparateShipping.query.get(1))
        order.set_status(OrderStatus.packed, self.actor)
        db.session.commit()

        self.assertEqual(order.total_base_currency, 10000 + 5000)  # subtotal + shipping

    def test_set_status_packed_non_separate_shipping_leaves_cost_unchanged(self):
        """Orders with NoShipping are not affected by the SeparateShipping hook"""
        order = self._make_order(NoShipping.query.get(999), shipping_base_currency=100)
        order.set_status(OrderStatus.packed, self.actor)

        self.assertEqual(order.shipping_base_currency, 100)  # unchanged

    def test_shipment_is_paid_status_exists_in_enum(self):
        self.assertIn('shipment_is_paid', [s.name for s in OrderStatus])
        self.assertEqual(OrderStatus.shipment_is_paid.value, 9)
