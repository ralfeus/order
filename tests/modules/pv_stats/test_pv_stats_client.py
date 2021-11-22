'''
Tests of pv_stats functionality client
'''
from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User

class TestPVStatsClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_pv_stats_client', email='root_test_pv_stats_client@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_pv_stats_client', email='root_test_pv_stats_client@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role
        ])

    def test_pv_stats_admin_client_page(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/pv_stats/permissions'))
        #self.client.get('/admin/pv_stats/') #TODO: Clarify if it's needed
        self.assertEqual(res.status_code, 200)

    def test_pv_stats_user_client_page(self):
        res = self.try_user_operation(
            lambda: self.client.get('/pv_stats/'))
        self.assertEqual(res.status_code, 200)
