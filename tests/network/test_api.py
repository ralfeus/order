'''
Tests of network builder manager
'''
from subprocess import Popen
from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User

class TestNetworkManager(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_netman_api', email='root_test_netman_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_netman_api', email='root_test_netman_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role
        ])

    def test_get_network_builder_status(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/network/builder/status'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['status'], 'not running') #type: ignore
        self.client.get('/api/v1/admin/network/builder/start')
        res = self.client.get('/api/v1/admin/network/builder/status')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['status'], 'running') #type: ignore
        self.client.get('/api/v1/admin/network/builder/stop')
