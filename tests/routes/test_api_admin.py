from flask import url_for
import unittest

from app import create_app, db
from app.config import TestConfig

app = create_app(TestConfig)
app.app_context().push()

from app.models import Currency, Order, Shipping, User

def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ))

def logout(client):
    return client.get('/logout')

class TestAdminApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.session.execute('pragma foreign_keys=on')

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

        db.create_all()
        db.session.add_all([
            Currency(code='RUR', rate=1),
            Currency(code='USD', rate=1),
            Shipping(id=1, name='shipping1'),
            User(id=0, username='admin', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            User(id=1, username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            User(id=2, username='user2', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            Order(id=1, user_id=2, shipping_method_id=1),
            Order(id=2, user_id=2)
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def try_admin_operation(self, operation):
        res = operation()
        self.assertTrue(res.status_code, 302)
        login(self.client, 'user1', '1')
        res = operation()
        self.assertTrue(res.status_code, 403)
        logout(self.client)
        login(self.client, 'admin', '1')
        return operation()

    def test_delete_user(self):
        self.try_admin_operation(
            lambda: self.client.delete(url_for('admin_api.delete_user', user_id=1)))
        res = self.client.delete(url_for('admin_api.delete_user', user_id=2))
        self.assertEqual(res.status_code, 409)

    def test_get_orders(self):
        res = self.try_admin_operation(
            lambda: self.client.get(url_for('admin_api.get_orders')))
        self.assertEqual(res.json, [
            {
                'id': '1',
                'customer': None,
                'invoice_id': None,
                'total': 0,
                'total_krw': 0,
                'total_rur': 0,
                'total_usd': 0,
                'shipping': 'shipping1',
                'user': 'user2',
                'when_created': ''
            },
            {
                'id': '2',
                'customer': None,
                'invoice_id': None,
                'total': 0,
                'total_krw': 0,
                'total_rur': 0,
                'total_usd': 0,
                'shipping': '',
                'user': 'user2',
                'when_created': ''
            }
        ])