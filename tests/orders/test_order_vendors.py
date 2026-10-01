'''
Tests of sale orders with products of several vendors having the same product ID
'''
from tests import BaseTestCase, db
from app.models import Country
from app.currencies.models import Currency
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.products.models import Product
from app.shipping.models.shipping import NoShipping, Shipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User

PASSWORD_HASH = 'pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576'


class TestOrderVendors(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user_order_vendors', email='u@name.com',
                         password_hash=PASSWORD_HASH, enabled=True)
        self.admin = User(username='admin_order_vendors', email='a@name.com',
                          password_hash=PASSWORD_HASH, enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Country(id='c1', name='country1'),
            Product(id='0001', vendor='Atomy', name='Atomy 1', price=10, weight=10),
            Product(id='0001', vendor='AtomyAza', name='AZA 1', price=20, weight=10),
            Product(id='Z9', vendor='AtomyAza', name='AZA Z9', price=30, weight=10),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=100),
            NoShipping(id=999),
        ])

    def _order_payload(self, items, seq_num=None):
        suborder = {'subcustomer': 'A000, Subcustomer1, P@ssw0rd', 'items': items}
        if seq_num is not None:
            suborder['seq_num'] = seq_num
        return {
            'customer_name': 'User1', 'address': 'Address1', 'city_eng': 'City1',
            'country': 'c1', 'zip': '0000', 'shipping': '1', 'phone': '1',
            'comment': '', 'suborders': [suborder]
        }

    def _create_order(self, items):
        self.login(self.user.username, '1')
        res = self.client.post('/api/v1/order', json=self._order_payload(items))
        self.assertEqual(res.status_code, 200)
        return res.json, db.session.get(Order, res.json['order_id'])

    @staticmethod
    def _lines(order):
        db.session.expire_all()
        return sorted((op.product.key, op.quantity) for op in order.order_products)

    def test_create_order_with_product_keys(self):
        _, order = self._create_order([
            {'item_code': '0001', 'product_key': 'AtomyAza:0001', 'quantity': '1'},
            {'item_code': '0001', 'product_key': 'Atomy:0001', 'quantity': '2'},
            {'item_code': 'Z9', 'quantity': '3'},
        ])
        self.assertEqual(self._lines(order),
                         [('Atomy:0001', 2), ('AtomyAza:0001', 1), ('AtomyAza:Z9', 3)])
        self.assertEqual(
            sorted((op.product_id, op.product_vendor) for op in order.order_products),
            [('0001', 'Atomy'), ('0001', 'AtomyAza'), ('Z9', 'AtomyAza')])

    def test_create_order_same_key_is_combined(self):
        _, order = self._create_order([
            {'item_code': '0001', 'product_key': 'AtomyAza:0001', 'quantity': '1'},
            {'item_code': '0001', 'product_key': 'AtomyAza:0001', 'quantity': '2'},
        ])
        self.assertEqual(self._lines(order), [('AtomyAza:0001', 3)])

    def test_create_order_ambiguous_code(self):
        result, order = self._create_order([
            {'item_code': '0001', 'quantity': '1'},
            {'item_code': 'Z9', 'quantity': '1'},
        ])
        self.assertEqual(self._lines(order), [('AtomyAza:Z9', 1)])
        self.assertIn('Atomy:0001', str(result['message']))
        self.assertIn('AtomyAza:0001', str(result['message']))

    def test_create_order_unknown_key(self):
        result, order = self._create_order([
            {'item_code': 'Z9', 'product_key': 'Atomy:Z9', 'quantity': '1'},
        ])
        self.assertEqual(self._lines(order), [])
        self.assertIn('Z9', str(result['message']))

    def test_save_order_matches_lines_by_product(self):
        _, order = self._create_order([
            {'item_code': '0001', 'product_key': 'Atomy:0001', 'quantity': '1'}])
        order_id, seq_num = order.id, order.suborders[0].seq_num
        line_id = order.order_products[0].id
        self.logout()
        self.login(self.admin.username, '1')
        # Same product: quantity is updated in the same line
        res = self.client.post(f'/api/v1/order/{order_id}', json=self._order_payload([
            {'item_code': '0001', 'product_key': 'Atomy:0001', 'quantity': '5'}], seq_num))
        self.assertEqual(res.status_code, 200)
        order = db.session.get(Order, order_id)
        self.assertEqual(self._lines(order), [('Atomy:0001', 5)])
        self.assertEqual(order.order_products[0].id, line_id)
        # Same code of other vendor: other product replaces the line
        res = self.client.post(f'/api/v1/order/{order_id}', json=self._order_payload([
            {'item_code': '0001', 'product_key': 'AtomyAza:0001', 'quantity': '2'}], seq_num))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._lines(db.session.get(Order, order_id)), [('AtomyAza:0001', 2)])

    def test_save_order_keeps_line_without_key(self):
        '''Lines of orders saved before vendors were introduced have no key in UI'''
        _, order = self._create_order([{'item_code': 'Z9', 'quantity': '1'}])
        order_id, seq_num = order.id, order.suborders[0].seq_num
        self.logout()
        self.login(self.admin.username, '1')
        res = self.client.post(f'/api/v1/order/{order_id}', json=self._order_payload(
            [{'item_code': 'Z9', 'quantity': '4'}], seq_num))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._lines(db.session.get(Order, order_id)), [('AtomyAza:Z9', 4)])

    def test_admin_change_order_product(self):
        _, order = self._create_order([
            {'item_code': '0001', 'product_key': 'Atomy:0001', 'quantity': '1'}])
        op_id = order.order_products[0].id
        self.logout()
        self.login(self.admin.username, '1')
        res = self.client.post(f'/api/v1/admin/order/product/{op_id}',
                               json={'product_id': 'AtomyAza:0001'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['product_key'], 'AtomyAza:0001')
        db.session.expire_all()
        self.assertEqual(db.session.get(OrderProduct, op_id).product_vendor, 'AtomyAza')

        res = self.client.post(f'/api/v1/admin/order/product/{op_id}',
                               json={'product_id': 'Z9'})
        self.assertEqual(res.json['product_key'], 'AtomyAza:Z9')
        # Same code as the current one means no change
        res = self.client.post(f'/api/v1/admin/order/product/{op_id}',
                               json={'product_id': 'Z9'})
        self.assertEqual(res.status_code, 200)
        res = self.client.post(f'/api/v1/admin/order/product/{op_id}',
                               json={'product_id': '0001'})
        self.assertEqual(res.status_code, 409)
        res = self.client.post(f'/api/v1/admin/order/product/{op_id}',
                               json={'product_id': 'nonexistent'})
        self.assertEqual(res.status_code, 404)
        db.session.expire_all()
        self.assertEqual(db.session.get(OrderProduct, op_id).product.key, 'AtomyAza:Z9')

    def test_order_product_to_dict(self):
        _, order = self._create_order([
            {'item_code': '0001', 'product_key': 'AtomyAza:0001', 'quantity': '1'}])
        result = order.order_products[0].to_dict()
        self.assertEqual(result['product_id'], '0001')
        self.assertEqual(result['product_vendor'], 'AtomyAza')
        self.assertEqual(result['product_key'], 'AtomyAza:0001')
