from tests import BaseTestCase, db

from app.users.models.role import Role
from app.users.models.user import User

class TestAdminRoleApi(BaseTestCase):
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
            admin_role, self.user, self.admin
        ])

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_roles(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/user/role'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)

