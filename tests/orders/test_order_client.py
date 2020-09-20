from datetime import datetime

from app.models import Currency, Order, Role, User
from app.invoices.models import Invoice

from tests import BaseTestCase, db

class TestOrdersClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.try_add_entities([
            User(username='orders_client_root', email='orders_client_root@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True, roles=[admin_role]),
            User(username='orders_client_user', email='orders_client_user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            admin_role
        ])

    def try_admin_operation(self, operation):
        return super().try_admin_operation(operation, 'orders_client_user', '1', 'orders_client_root', '1')
    
    def test_print_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order()
        ])
        self.try_admin_operation(
            lambda: self.client.get(f'/admin/orders/{gen_id}'))

