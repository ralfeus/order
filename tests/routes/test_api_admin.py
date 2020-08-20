from flask import url_for
from datetime import datetime
import unittest

from app import create_app, db
from app.config import TestConfig

app = create_app(TestConfig)
app.app_context().push()

from app.models import Currency, Invoice, Order, Role, Shipping, User

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
        # db.session.execute('SET default_storage_engine=MEMORY')

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

        db.create_all()
        admin_role = Role(id=1, name='admin')
        db.session.add_all([
            Currency(code='RUR', rate=1),
            Currency(code='USD', rate=1),
            Invoice(id='INV-2020-00-00', 
                when_created=datetime(2020, 1, 1, 1, 0, 0),
                when_changed=datetime(2020, 1, 1, 1, 0, 0)),
            Order(id=1, user_id=2, shipping_method_id=1),
            Order(id=2, user_id=2, invoice_id='INV-2020-00-00'),
            Shipping(id=1, name='shipping1'),
            User(id=0, username='root', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True, roles=[admin_role]),
            User(id=1, username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            User(id=2, username='user2', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            admin_role
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
        login(self.client, 'root', '1')
        return operation()

    def test_get_invoices(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice'))
        res = self.client.get('/api/v1/admin/invoice/INV-2020-00-00')
        self.assertEqual(res.json, [
            {
                'address': None, 
                'country': None, 
                'customer': None, 
                'id': 'INV-2020-00-00', 
                'order_products': [], 
                'orders': ['2'], 
                'phone': None, 
                'total': 0, 
                'weight': 0, 
                'when_changed': '2020-01-01 01:00:00', 
                'when_created': '2020-01-01 01:00:00'
            }
        ])

    def test_create_invoice(self):
        self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/invoice/new'))

    def test_get_invoice_excel(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/0/excel/0'))

    def test_get_orders(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/order'))
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
                'invoice_id': 'INV-2020-00-00',
                'total': 0,
                'total_krw': 0,
                'total_rur': 0,
                'total_usd': 0,
                'shipping': '',
                'user': 'user2',
                'when_created': ''
            }
        ])

    def test_get_order_products(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/v1/order_product'))

    def test_save_order_product(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/admin/v1/order_product'))

    def test_set_order_product_status(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/admin/v1/order_product/0/status/0'))

    def test_get_order_product_status_history(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/v1/order_product/0/status/history'))

    def test_get_product(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/v1/product'))

    def test_save_product(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/admin/v1/product'))

    def test_delete_product(self):
        res = self.try_admin_operation(
            lambda: self.client.delete('/admin/v1/product/0'))

    def test_get_transactions(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/v1/transaction'))

    def test_save_transaction(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/admin/v1/transaction'))

    def test_delete_user(self):
        self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/user/1'))
        res = self.client.delete('/api/v1/admin/user/2')
        self.assertEqual(res.status_code, 409)

    def test_save_user(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/admin/v1/user'))