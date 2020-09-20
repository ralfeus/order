from datetime import datetime

from tests import BaseTestCase, db
from app.models import Country, Currency, Product, Role, Shipping, ShippingRate, User
from app.orders.models import Order, OrderProduct

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
            Currency(code='RUR', rate=0.5)
        ])

    def try_admin_operation(self, operation):
        '''
        Superseeds base method to add class-specific user and admin credentials
        '''
        return super().try_admin_operation(operation,
            self.user.username, '1', self.admin.username, '1')
    
    def try_user_operation(self, operation):
        '''
        Superseeds base method to add class-specific user credentials
        '''
        return super().try_user_operation(operation,
            self.user.username, '1')
        
    def test_create_order(self):
        created_order_id = None
        self.try_add_entities([
            Country(id='c1', name='country1'),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(id=1, shipping_method_id=1, destination='c1', weight=100, rate=100),
            Product(id='0001', name='Korean name 1', name_english='English name', name_russian='Russian name', price=1, available=True)
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
                        "items": [{"item_code":"0001", "quantity":"1"}]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(order.total_krw, 101)
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

    def test_get_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Product(id=gen_id, price=10, weight=10),
            Order(id=gen_id, user=self.user),
            OrderProduct(order_id=gen_id, product_id=gen_id, price=10, quantity=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.get(f'/api/v1/order/{gen_id}'))
        self.assertEqual(res.json, {
            'id': gen_id,
            'address': None,
            'phone': None,
            'customer': None,
            'invoice_id': None,
            'shipping': {'id': 1, 'name': 'No shipping'},
            'country': None,
            'status': '',
            'total': 100,
            'total_krw': 100,
            'total_rur': 50.0,
            'total_usd': 50.0,
            'tracking_id': '',
            'tracking_url': '',
            'user': self.user.username,
            'when_changed': '',
            'when_created': '',
            'order_products': [
                {
                    'id': 1,
                    'order_id': gen_id,
                    'suborder_id': None,
                    'order_product_id': 1,
                    'customer': None,
                    'subcustomer': None,
                    'private_comment': None,
                    'public_comment': None,
                    'product_id': gen_id,
                    'product': None,
                    'name': None,
                    'name_english': None,
                    'name_russian': None,
                    'price': 10,
                    'points': None,
                    'quantity': 10,
                    'status': None,
                    'weight': 10,
                    'buyout_date': None
                }
            ]
        })
