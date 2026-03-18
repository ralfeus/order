'''
Tests of network builder manager
'''
from unittest.mock import patch, MagicMock
from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User

def _make_mock_requests_get(state):
    '''Returns a mock for requests.get that simulates the network builder service.
    State is a mutable dict so the closure can share it across calls.'''
    def mock_get(url, **kwargs):
        response = MagicMock()
        if '/builder/start' in url:
            state['running'] = True
            response.content = b'{"status": "started"}'
        elif '/builder/stop' in url:
            state['running'] = False
            response.content = b'{"status": "stopped"}'
        elif '/builder/status' in url:
            status = 'running' if state['running'] else 'not running'
            response.content = f'{{"status": "{status}"}}'.encode()
        else:
            response.content = b'{"status": "unknown"}'
        return response
    return mock_get

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

        self._builder_state = {'running': False}
        self._requests_patcher = patch(
            'app.network.routes.api.requests.get',
            side_effect=_make_mock_requests_get(self._builder_state)
        )
        self._requests_patcher.start()

    def tearDown(self):
        self.client.get('/api/v1/admin/network/builder/stop')
        self._requests_patcher.stop()
        return super().tearDown()

    def test_get_network_builder_status(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/network/builder/status'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['status'], 'not running') #type: ignore
        self.client.get('/api/v1/admin/network/builder/start')
        res = self.client.get('/api/v1/admin/network/builder/status')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['status'], 'running') #type: ignore

    def test_start_with_emtpy_nodes(self):
        with patch('time.sleep'):
            self.try_admin_operation(
                lambda: self.client.get('/api/v1/admin/network/builder/start?nodes='))
        res = self.client.get('/api/v1/admin/network/builder/status')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['status'], 'running') #type: ignore
