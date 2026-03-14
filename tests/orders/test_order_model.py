"""
Tests for Order model currency methods (Subtask 1: DB Migration + Order Model Refactor)
"""
from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.models.country import Country
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.orders.models.order_product import OrderProduct
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.shipping.models.shipping import NoShipping, Shipping, ShippingRate
from app.users.models.user import User


class TestOrderModelCurrency(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        self.base_currency = Currency(code='KRW', rate=1, base=True)
        self.usd = Currency(code='USD', rate=0.001)   # 1 KRW = 0.001 USD
        self.eur = Currency(code='EUR', rate=0.0009)  # 1 KRW = 0.0009 EUR
        self.user = User(
            username='test_order_model_user',
            email='test_order_model@test.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True,
        )
        self.country = Country(id='KR', name='South Korea')
        self.no_shipping = NoShipping(id=999)
        self.try_add_entities([
            self.base_currency, self.usd, self.eur,
            self.user, self.country, self.no_shipping,
        ])

    def _make_order(self, currency_code='USD', total_krw=100000,
                    total_user_currency=100.0, shipping_krw=10000,
                    shipping_user_currency=10.0, subtotal_krw=90000,
                    subtotal_user_currency=90.0):
        """Helper to create an order with preset currency amounts."""
        order = Order(user=self.user, status=OrderStatus.pending)
        order.currency_code = currency_code
        order.total_krw = total_krw
        order.total_user_currency = total_user_currency
        order.shipping_krw = shipping_krw
        order.shipping_user_currency = shipping_user_currency
        order.subtotal_krw = subtotal_krw
        order.subtotal_user_currency = subtotal_user_currency
        self.try_add_entity(order)
        return order

    # --- get_total() tests ---

    def test_get_total_no_currency_returns_krw(self):
        """get_total() with no argument returns base (KRW) amount."""
        order = self._make_order(total_krw=100000, total_user_currency=100.0)
        self.assertEqual(order.get_total(), 100000)

    def test_get_total_base_currency_returns_krw(self):
        """get_total(base_currency) returns base (KRW) amount."""
        order = self._make_order(total_krw=100000, total_user_currency=100.0)
        self.assertEqual(order.get_total(self.base_currency), 100000)

    def test_get_total_matching_user_currency_returns_precomputed(self):
        """get_total() with currency matching order.currency_code returns stored amount."""
        order = self._make_order(currency_code='USD', total_krw=100000, total_user_currency=100.0)
        result = order.get_total(self.usd)
        self.assertEqual(result, 100.0)

    def test_get_total_arbitrary_currency_converts_from_krw(self):
        """get_total() with a currency different from order.currency_code converts on the fly."""
        order = self._make_order(currency_code='USD', total_krw=100000, total_user_currency=100.0)
        # EUR rate = 0.0009, so 100000 * 0.0009 = 90.0
        result = order.get_total(self.eur)
        self.assertAlmostEqual(float(result), 90.0, places=2)

    def test_get_total_none_user_currency_falls_back_to_conversion(self):
        """get_total() when stored user_currency amount is 0/None uses conversion."""
        order = self._make_order(currency_code='USD', total_krw=100000, total_user_currency=0)
        result = order.get_total(self.usd)
        # Falls back to conversion: 100000 * 0.001 = 100.0
        self.assertAlmostEqual(float(result), 100.0, places=2)

    # --- get_shipping() tests ---

    def test_get_shipping_no_currency_returns_krw(self):
        order = self._make_order(shipping_krw=10000, shipping_user_currency=10.0)
        self.assertEqual(order.get_shipping(), 10000)

    def test_get_shipping_base_currency_returns_krw(self):
        order = self._make_order(shipping_krw=10000, shipping_user_currency=10.0)
        self.assertEqual(order.get_shipping(self.base_currency), 10000)

    def test_get_shipping_user_currency_returns_precomputed(self):
        order = self._make_order(currency_code='USD', shipping_krw=10000, shipping_user_currency=10.0)
        self.assertEqual(order.get_shipping(self.usd), 10.0)

    def test_get_shipping_arbitrary_currency_converts(self):
        order = self._make_order(currency_code='USD', shipping_krw=10000, shipping_user_currency=10.0)
        result = order.get_shipping(self.eur)
        self.assertAlmostEqual(float(result), 9.0, places=2)

    # --- get_subtotal() tests ---

    def test_get_subtotal_no_currency_returns_krw(self):
        order = self._make_order(subtotal_krw=90000, subtotal_user_currency=90.0)
        self.assertEqual(order.get_subtotal(), 90000)

    def test_get_subtotal_base_currency_returns_krw(self):
        order = self._make_order(subtotal_krw=90000, subtotal_user_currency=90.0)
        self.assertEqual(order.get_subtotal(self.base_currency), 90000)

    def test_get_subtotal_user_currency_returns_precomputed(self):
        order = self._make_order(currency_code='USD', subtotal_krw=90000, subtotal_user_currency=90.0)
        self.assertEqual(order.get_subtotal(self.usd), 90.0)

    def test_get_subtotal_arbitrary_currency_converts(self):
        order = self._make_order(currency_code='USD', subtotal_krw=90000, subtotal_user_currency=90.0)
        result = order.get_subtotal(self.eur)
        self.assertAlmostEqual(float(result), 81.0, places=2)

    # --- to_dict() tests ---

    def test_to_dict_includes_currency_code(self):
        """to_dict() must include currency_code field."""
        order = self._make_order(currency_code='USD', total_krw=100000, total_user_currency=100.0)
        result = order.to_dict()
        self.assertIn('currency_code', result)
        self.assertEqual(result['currency_code'], 'USD')

    def test_to_dict_includes_total_user_currency(self):
        """to_dict() must include total_user_currency instead of total_cur1/total_cur2."""
        order = self._make_order(currency_code='USD', total_krw=100000, total_user_currency=100.0)
        result = order.to_dict()
        self.assertIn('total_user_currency', result)
        self.assertAlmostEqual(result['total_user_currency'], 100.0, places=2)

    def test_to_dict_does_not_include_hardcoded_cur1_cur2(self):
        """to_dict() must not contain the old hardcoded total_cur1 / total_cur2 keys."""
        order = self._make_order(currency_code='USD', total_krw=100000, total_user_currency=100.0)
        result = order.to_dict()
        self.assertNotIn('total_cur1', result)
        self.assertNotIn('total_cur2', result)

    # --- update_total() tests ---

    def test_update_total_stores_user_currency_amounts(self):
        """update_total() computes user_currency amounts using order.currency_code rate."""
        product = Product(id='T001', name='Test', price=10000, weight=100)
        self.try_add_entity(product)
        order = Order(user=self.user, status=OrderStatus.pending)
        order.currency_code = 'USD'
        order.country = self.country
        order.shipping = self.no_shipping
        self.try_add_entity(order)
        suborder = Suborder(order=order)
        self.try_add_entity(suborder)
        op = OrderProduct(suborder=suborder, product_id='T001', quantity=2)
        self.try_add_entity(op)

        order.update_total()

        # subtotal = 10000 * 2 = 20000 KRW + 2500 local shipping (below threshold) = 22500
        self.assertEqual(order.subtotal_krw, 22500)
        # subtotal_user_currency = 22500 * 0.001 = 22.5 USD
        self.assertAlmostEqual(float(order.subtotal_user_currency), 22.5, places=2)
        # NoShipping has no cost, so shipping = 0
        self.assertEqual(order.shipping_krw, 0)
        self.assertEqual(float(order.shipping_user_currency), 0.0)
        # total_krw = 22500
        self.assertEqual(order.total_krw, 22500)
        # total_user_currency = 22.5
        self.assertAlmostEqual(float(order.total_user_currency), 22.5, places=2)

    def test_update_total_base_currency_sets_zero_user_amounts(self):
        """update_total() when currency_code is base (KRW), user_currency amounts are 0."""
        product = Product(id='T002', name='Test2', price=10000, weight=100)
        self.try_add_entity(product)
        order = Order(user=self.user, status=OrderStatus.pending)
        order.currency_code = 'KRW'
        order.country = self.country
        order.shipping = self.no_shipping
        self.try_add_entity(order)
        suborder = Suborder(order=order)
        self.try_add_entity(suborder)
        op = OrderProduct(suborder=suborder, product_id='T002', quantity=1)
        self.try_add_entity(op)

        order.update_total()

        # subtotal = 10000 + 2500 local shipping (below 30000 threshold) = 12500
        self.assertEqual(order.subtotal_krw, 12500)
        # Base currency — user_currency amounts should be 0 (no conversion needed)
        self.assertEqual(float(order.subtotal_user_currency), 0.0)
        self.assertEqual(float(order.total_user_currency), 0.0)
