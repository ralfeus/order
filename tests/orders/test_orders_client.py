from datetime import datetime
from app.models import Currency, Role, User
from app.orders.models import Order

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
    
    def test_new_order(self):
        res = self.try_user_operation(
            lambda: self.client.get('/orders/new'))
        self.assertEqual(res.status_code, 200)

    def test_print_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order()
        ])
        self.try_admin_operation(
            lambda: self.client.get(f'/admin/orders/{gen_id}'))

    def test_user_orders_list(self):
        res = self.try_user_operation(
            lambda: self.client.get('/orders/')
        )
        self.assertEqual(res.status_code, 200)