'''
Tests of notifications functionality client
'''
from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User

class TestPaymentsClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_notifications_api', email='root_test_notifications_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_notifications_api', email='root_test_notifications_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role
        ])

    def test_create_notification(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/notifications/'))
        self.assertEqual(res.status_code, 200)
