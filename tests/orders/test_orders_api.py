from datetime import datetime

from tests import BaseTestCase, db
from app.models import Country, Role, Shipping, ShippingRate, User
from app.currencies.models import Currency
from app.orders.models import Order, OrderProduct, OrderProductStatusEntry, \
    OrderStatus, Subcustomer, Suborder
from app.products.models import Product

class TestOrdersApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_orders_api', email='root_test_orders_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_orders_api', email='root_test_orders_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='RUR', rate=0.5),
            Country(id='c1', name='country1'),
            Product(id='0000', name='Test product', price=10, weight=10),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=100),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=200),
        ])

    def test_create_order(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "name":"User1",
                "address":"Address1",
                "country":"c1",
                "shipping":"1",
                "phone":"",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(order.total_krw, 2620)
        self.assertEqual(order.shipping.name, 'Shipping1')

    def test_save_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id, user=self.user)
        ])
        res = self.try_user_operation(
            lambda: self.client.post(f'/api/v1/order/{gen_id}', json={
                'customer': 'Test'
            }))
        self.assertEqual(res.status_code, 200)

    def test_increase_order_amount_over_free_shipping_threshold(self):
        order = Order(user=self.user)
        subcustomer = Subcustomer(name='A000')
        suborder = Suborder(order=order, subcustomer=subcustomer)
        self.try_add_entities([
            order, suborder, subcustomer,
            OrderProduct(suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post(f'/api/v1/order/{order.id}', json={
                'suborders': [
                    {
                        'subcustomer': 'A000',
                        'items': [
                            {
                                'item_code': '0000',
                                'quantity': 3000
                            }
                        ]
                    }
                ]
            }))
        order = Order.query.get(order.id)
        self.assertEqual(order.total_krw, 30000)

    def test_get_orders(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user, country_id='c1', shipping_method_id=1)
        suborder = Suborder(order=order)
        self.try_add_entities([
            order, suborder,
            OrderProduct(id=10, suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/order'))
        self.assertEqual(res.json[0], {
            'id': gen_id,
            'customer': None,
            'invoice_id': None,
            'address': None,
            'country': {'id': 'c1', 'name': 'country1', 'sort_order': 999},
            'phone': None,
            'subtotal_krw': 2600,
            'shipping_krw': 100,
            'total': 2700,
            'total_krw': 2700,
            'total_rur': 1350.0,
            'total_usd': 1350.0,
            'shipping': {'id': 1, 'name': 'Shipping1'},
            'tracking_id': None,
            'tracking_url': None,
            'user': 'user1_test_orders_api',
            'status': None,
            'when_created': None,
            'when_changed': None,
            'order_products': [
                {
                    'id': 10,
                    'order_id': gen_id,
                    'suborder_id': suborder.id,
                    'order_product_id': 10,
                    'customer': None,
                    'subcustomer': None,
                    'subcustomer_id': None,
                    'private_comment': None,
                    'public_comment': None,
                    'product_id': '0000',
                    'product': None,
                    'name': 'Test product',
                    'name_english': None,
                    'name_russian': None,
                    'price': 10,
                    'points': None,
                    'quantity': 10,
                    'status': None,
                    'weight': 10,
                    'buyout_date': None,
                    'when_created': None,
                    'when_changed': None
                }
            ]
        })

    def test_get_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user)
        suborder = Suborder(order=order)
        self.try_add_entities([
            order, suborder,
            Product(id=gen_id, price=10, weight=10),
            OrderProduct(suborder=suborder, product_id=gen_id, price=10, quantity=10),
            Order(id=gen_id+'1', user=self.user, status=OrderStatus.pending)
        ])
        res = self.try_user_operation(
            lambda: self.client.get(f'/api/v1/order/{gen_id}'))
        self.assertEqual(res.json['total'], 2600)
        self.assertEqual(res.json['total_rur'], 1300.0)
        self.assertEqual(res.json['total_usd'], 1300.0)
        self.assertEqual(res.json['user'], self.user.username)
        self.assertEqual(len(res.json['order_products']), 1)
        res = self.client.get('/api/v1/order')
        self.assertEqual(len(res.json), 2)
        res = self.client.get('/api/v1/order?status=pending')
        self.assertEqual(res.json[0]['status'], 'pending')

    def test_get_order_products(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        subcustomer = Subcustomer()
        suborder = Suborder(order_id=gen_id, subcustomer=subcustomer)
        self.try_add_entities([
            Order(id=gen_id, user_id=self.user.id, status=OrderStatus.pending, country_id='c1',
                  shipping_method_id=1,
                  tracking_id='T00', tracking_url='https://tracking.fake/T00'),
            subcustomer,
            suborder
        ])
        
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/admin/order/product'))

    def test_save_order_product(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        op_id = datetime.now().microsecond
        self.try_add_entities([
            Order(id=gen_id, user=self.user),
            Suborder(id=op_id, order_id=gen_id),
            OrderProduct(id=op_id, suborder_id=op_id, product_id='0000', price=10, quantity=10)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/product/{op_id}', json={
            'quantity': 100
        }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['quantity'], 100)

        res = self.client.get(f'/api/v1/admin/order/{gen_id}')
        self.assertTrue(res.json['total_krw'], 1010)

    def test_set_order_product_status(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        op_id = datetime.now().microsecond
        self.try_add_entities([
            Order(id=gen_id, user=self.user),
            Suborder(id=op_id, order_id=gen_id),
            OrderProduct(id=op_id, suborder_id=op_id, product_id='0000', price=10, quantity=10)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/product/{op_id}/status/0'))

    def test_get_order_product_status_history(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        subcustomer = Subcustomer()
        suborder = Suborder(order_id=gen_id, subcustomer=subcustomer)
        self.try_add_entities([
            Order(id=gen_id, user_id=self.user.id, status='pending', country_id='c1',
                  tracking_id='T00', tracking_url='https://tracking.fake/T00'),
            subcustomer,
            suborder,
            OrderProduct(id=10, suborder=suborder, product_id='0000', price=10, quantity=10),
            OrderProductStatusEntry(order_product_id=10, user_id=self.admin.id,
                set_at=datetime(2020, 1, 1, 1, 0, 0), status="Pending")
        ])
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/order/product/10/status/history'))
        res = self.client.get('/api/v1/admin/order/product/10/status/history')
        self.assertEqual(res.json, [{
            'set_at': '2020-01-01 01:00:00',
            'set_by': 'root_test_orders_api',
            'status': 'Pending'
        }])
        res = self.client.get('/api/v1/admin/order/product/30/status/history')
        self.assertEqual(res.status_code, 404)

    def test_validate_subcustomer(self):
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order/subcustomer/validate', json={
                'subcustomer': 'test, test, test'
            }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['result'], 'failure')
        res = self.client.post('/api/v1/order/subcustomer/validate', json={
                'subcustomer': '23426444, Mike, atomy#01'
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['result'], 'success')
