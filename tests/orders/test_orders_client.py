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
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=0.5),
            Country(id='c1', name='country1'),
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
            Country(id='c1', name='country1'),
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
        created_order_id = res.json['order_id']
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