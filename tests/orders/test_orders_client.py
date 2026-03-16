from datetime import datetime
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.order_status import OrderStatus
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.users.models.role import Role
from app.users.models.user import User
from app.models import Country
from app.currencies.models import Currency
from app.products.models import Product

from tests import BaseTestCase, db

class TestOrdersClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_orders_client', email='root_test_orders_client@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_orders_client', email='root_test_orders_client@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='KRW', rate=1, base=True),
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=0.5),
            Country(id='c1', name='country1', locale='ko-KR', currency_code='KRW'),
            Product(id='0000', name='Test product', price=10, weight=10),
        ])
    
    def test_new_order(self):
        res = self.try_user_operation(
            lambda: self.client.get('/orders/new'))
        self.assertEqual(res.status_code, 200)

    def test_print_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order()
        ])
        self.try_user_operation(
            lambda: self.client.get(f'/admin/orders/{gen_id}'))

    def test_user_orders_list(self):
        res = self.try_user_operation(
            lambda: self.client.get('/orders/')
        )
        self.assertEqual(res.status_code, 200)

    def test_user_order_drafts_list(self):
        res = self.try_user_operation(
            lambda: self.client.get('/orders/drafts')
        )
        self.assertEqual(res.status_code, 200)

    def test_user_get_order(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10),
            Country(id='c1', name='country1', locale='cz-CZ', currency_code='CZK'),
            Currency(code='CZK', rate=1)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "city_eng":"City1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0001", "quantity":"1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id'] #type: ignore
        res = self.client.get(f'/orders/{created_order_id}?currency=CZK')


    def test_get_order_excel(self):
        order = Order(
            user=self.user, status=OrderStatus.shipped, when_created=datetime.now(),
            country_id='c1')
        suborder = Suborder(order=order, subcustomer=Subcustomer(username='user1'))
        self.try_add_entities([
            order, suborder,
            OrderProduct(suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.get(f'/orders/{order.id}/excel')
        )
        self.assertEqual(res.status_code, 200)

    def test_admin_get_distribution_list(self):
        # Create test orders with necessary data for distribution list
        order1 = Order(
            id='ORD-DL-001',
            user=self.user,
            status=OrderStatus.shipped,
            when_created=datetime.now(),
            country_id='c1',
            customer_name='Customer 1',
            email='customer1@test.com',
            phone='123456789',
            address='123 Test Street',
            zip='12345',
            city_eng='Test City 1',
            total_weight=1000
        )
        order2 = Order(
            id='ORD-DL-002',
            user=self.user,
            status=OrderStatus.shipped,
            when_created=datetime.now(),
            country_id='c1',
            customer_name='Customer 2',
            email='customer2@test.com',
            phone='987654321',
            address='456 Test Avenue',
            zip='54321',
            city_eng='Test City 2',
            total_weight=2000
        )
        self.try_add_entities([order1, order2])

        # Test without URL parameter (includes authorization checks)
        res = self.try_admin_operation(
            lambda: self.client.get(
                f'/admin/orders/distribution_list?order_ids={order1.id},{order2.id}'
            )
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # Test with URL parameter (already logged in as admin)
        res = self.client.get(
            f'/admin/orders/distribution_list?order_ids={order1.id},{order2.id}&url=https://example.com/tracking'
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # Verify we got a non-empty Excel file
        self.assertGreater(len(res.data), 0)

    def test_distribution_list_saves_tracking_url(self):
        '''Tracking URL provided in the request is persisted on all specified orders'''
        order1 = Order(
            id='ORD-TRK-001',
            user=self.user,
            status=OrderStatus.shipped,
            when_created=datetime.now(),
            country_id='c1',
            customer_name='Customer 1',
            email='customer1@test.com',
            phone='123456789',
            address='123 Test Street',
            zip='12345',
            city_eng='Test City 1',
            total_weight=1000
        )
        order2 = Order(
            id='ORD-TRK-002',
            user=self.user,
            status=OrderStatus.shipped,
            when_created=datetime.now(),
            country_id='c1',
            customer_name='Customer 2',
            email='customer2@test.com',
            phone='987654321',
            address='456 Test Avenue',
            zip='54321',
            city_eng='Test City 2',
            total_weight=2000
        )
        self.try_add_entities([order1, order2])

        tracking_url = 'https://tracking.example.com/track/12345'
        self.login(self.admin.username, '1')
        res = self.client.get(
            f'/admin/orders/distribution_list'
            f'?order_ids={order1.id},{order2.id}'
            f'&tracking_url={tracking_url}'
        )
        self.assertEqual(res.status_code, 200)

        db.session.expire_all()
        updated_order1 = Order.query.get(order1.id)
        updated_order2 = Order.query.get(order2.id)
        self.assertEqual(updated_order1.tracking_url, tracking_url)
        self.assertEqual(updated_order2.tracking_url, tracking_url)

    def test_new_order_stores_user_currency(self):
        '''Creating an order stores the user preferred currency on the order'''
        from app.shipping.models.shipping import NoShipping
        self.try_add_entities([
            NoShipping(id=1),
            Country(id='c2', name='country2', locale='en-US', currency_code='USD'),
        ])
        self.user.currency_code = 'USD'
        db.session.commit()
        self.login(self.user.username, '1')
        res = self.client.post('/api/v1/order', json={
            'customer_name': 'User1',
            'address': 'Address1',
            'city_eng': 'City1',
            'country': 'c2',
            'zip': '0000',
            'shipping': '1',
            'phone': '1',
            'suborders': [{'subcustomer': 'A001, Sub1, P@ssw0rd',
                           'items': [{'item_code': '0000', 'quantity': '1'}]}]
        })
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(res.json['order_id'])
        self.assertEqual(order.user_currency_code, 'USD')

    def test_new_order_falls_back_to_base_currency(self):
        '''Creating an order with no user currency preference uses base currency'''
        from app.shipping.models.shipping import NoShipping
        self.try_add_entities([
            NoShipping(id=2),
            Country(id='c3', name='country3', locale='en-US', currency_code='USD'),
        ])
        self.user.currency_code = None
        db.session.commit()
        self.login(self.user.username, '1')
        res = self.client.post('/api/v1/order', json={
            'customer_name': 'User1',
            'address': 'Address1',
            'city_eng': 'City1',
            'country': 'c3',
            'zip': '0000',
            'shipping': '2',
            'phone': '1',
            'suborders': [{'subcustomer': 'A002, Sub2, P@ssw0rd',
                           'items': [{'item_code': '0000', 'quantity': '1'}]}]
        })
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(res.json['order_id'])
        self.assertEqual(order.user_currency_code, 'KRW')

    def test_user_currency_preference_stored_in_column(self):
        '''User.currency_code column stores and retrieves currency preference'''
        self.user.currency_code = 'EUR'
        db.session.commit()
        db.session.expire(self.user)
        self.assertEqual(self.user.currency_code, 'EUR')

    def test_get_profile_includes_currency_from_column(self):
        '''get_profile() includes currency_code when not in profile JSON'''
        self.user.currency_code = 'USD'
        self.user.profile = '{}'
        db.session.commit()
        profile = self.user.get_profile()
        self.assertEqual(profile.get('currency'), 'USD')

    def test_set_profile_updates_currency_column(self):
        '''set_profile() with currency key updates currency_code column'''
        self.user.set_profile({'currency': 'EUR'})
        self.assertEqual(self.user.currency_code, 'EUR')

    def test_distribution_list_tracking_url_not_applied_to_other_orders(self):
        '''Tracking URL is only saved on the orders specified in order_ids'''
        order_in = Order(
            id='ORD-TRK-IN',
            user=self.user,
            status=OrderStatus.shipped,
            when_created=datetime.now(),
            country_id='c1',
            customer_name='Customer In',
            email='in@test.com',
            phone='111111111',
            address='1 Main St',
            zip='10000',
            city_eng='City In',
            total_weight=500
        )
        order_out = Order(
            id='ORD-TRK-OUT',
            user=self.user,
            status=OrderStatus.shipped,
            when_created=datetime.now(),
            country_id='c1',
            customer_name='Customer Out',
            email='out@test.com',
            phone='222222222',
            address='2 Side St',
            zip='20000',
            city_eng='City Out',
            total_weight=600
        )
        self.try_add_entities([order_in, order_out])

        tracking_url = 'https://tracking.example.com/track/99999'
        self.login(self.admin.username, '1')
        res = self.client.get(
            f'/admin/orders/distribution_list'
            f'?order_ids={order_in.id}'
            f'&tracking_url={tracking_url}'
        )
        self.assertEqual(res.status_code, 200)

        db.session.expire_all()
        self.assertEqual(Order.query.get(order_in.id).tracking_url, tracking_url)
        self.assertIsNone(Order.query.get(order_out.id).tracking_url)