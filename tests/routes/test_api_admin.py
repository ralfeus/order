from datetime import datetime

from tests import BaseTestCase, db

from app.orders.models import Order
from app.models import Role, User

class TestAdminApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None

        db.create_all()
        admin_role = Role(id=10, name='admin')
        self.admin = User(id=0, username='root', email='user@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.user = User(id=10, username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True)
        self.try_add_entities([
            admin_role, self.user, self.admin,
            User(id=20, username='user2', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            Order(id='test-api-admin-2', user_id=20)
        ])

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_delete_user(self):
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/user/20'))
        self.assertEqual(res.status_code, 409)

    def test_save_user(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/user/0'))
        self.assertEqual(res.status_code, 400)
