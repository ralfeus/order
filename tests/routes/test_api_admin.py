from flask import Response
from datetime import datetime
import unittest

from app import create_app, db
from app.config import TestConfig

app = create_app(TestConfig)
app.app_context().push()

from app.models import Country, Currency, Invoice, Order, OrderProduct, \
    OrderProductStatusEntry, Product, Role, Shipping, ShippingRate, User

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
        self.maxDiff = None

        db.create_all()
        admin_role = Role(id=10, name='admin')
        try:
            db.session.add_all([
                Country(id='c1', name='country1'),
                Currency(code='RUR', rate=1),
                Currency(code='USD', rate=1),
                Invoice(id='INV-2020-00-00', 
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0)),
                Order(id=10, user_id=20, shipping_method_id=10, country='c1',
                    tracking_id='T00', tracking_url='https://tracking.fake/T00', status='shipped'),
                Order(id=20, user_id=20, invoice_id='INV-2020-00-00', status='pending', country='c1'),
                Product(id='0010', name='Test product'),
                Shipping(id=10, name='shipping1'),
                ShippingRate(id=10, shipping_method_id=10, destination='c1', weight=1000, rate=10),
                User(id=0, username='root', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True, roles=[admin_role]),
                User(id=10, username='user1', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True),
                User(id=20, username='user2', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True),
                admin_role
            ])
            db.session.add_all([
                OrderProduct(id=10, order_id=10, product_id='0010', price=10, quantity=10),
                OrderProductStatusEntry(order_product_id=10, user_id=10, 
                    set_at=datetime(2020, 1, 1, 1, 0, 0), status="Pending")
            ])
            db.session.commit()
        except:
            db.session.rollback()

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
        self.assertEqual(res.json[0], {
            'address': None,
            'country': 'c1',
            'customer': None, 
            'id': 'INV-2020-00-00', 
            'order_products': [], 
            'orders': ['20'], 
            'phone': None, 
            'total': 0, 
            'weight': 0, 
            'when_changed': '2020-01-01 01:00:00', 
            'when_created': '2020-01-01 01:00:00'
        })

    def test_create_invoice(self):
        self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/invoice/new'))

    def test_get_invoice_excel(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/0/excel/0'))

    def test_get_invoice_cumulative_excel(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/excel?invoices[0]=INV-2020-00-00&invoices[0]=INV-2020-00-00'))
        res = self.client.get('/api/v1/admin/invoice/excel?invoices[0]=INV-2020-00-00&invoices[0]=INV-2020-00-00')
        self.assertTrue(isinstance(res, Response))

    def test_get_orders(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/order'))
        self.assertEqual(res.json[0], {
            'id': '10',
            'customer': None,
            'invoice_id': None,
            'total': 100,
            'total_krw': 100,
            'total_rur': 100,
            'total_usd': 100,
            'shipping': 'shipping1',
            'tracking_id': 'T00',
            'tracking_url': 'https://tracking.fake/T00',
            'user': 'user2',
            'status': 'shipped',
            'when_created': '',
            'when_changed': ''
        })
        self.assertEqual(res.json[1], {
            'id': '20',
            'customer': None,
            'invoice_id': 'INV-2020-00-00',
            'total': 0,
            'total_krw': 0,
            'total_rur': 0,
            'total_usd': 0,
            'shipping': 'No shipping',
            'user': 'user2',
            'tracking_id': '',
            'tracking_url': '',
            'status': 'pending',
            'when_created': '',
            'when_changed': ''
        })

    def test_save_order(self):
        self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/order/10',
                json={'tracking_id': 'T00', 'tracking_url': 'https://tracking.fake/T00'}
            )
        )
        res = self.client.post(
            '/api/v1/admin/order/10',
            json={
                'id':10, 'tracking_id': 'T00', 'tracking_url': 'https://tracking.fake/T00',
                'status': 'done'
            }
        )
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/api/v1/admin/order/10')
        self.assertEqual(res.get_json()[0]['tracking_id'], 'T00')
        self.assertEqual(res.get_json()[0]['tracking_url'], 'https://tracking.fake/T00')
        self.assertEqual(res.get_json()[0]['status'], 'done')

    def test_get_order_products(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/order_product'))

    def test_save_order_product(self):
        self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/order_product/10'))
        res = self.client.post('/api/v1/admin/order_product/10', json={
            'quantity': 100
        })
        self.assertEqual(res.json, {
            'comment': None, 
            'customer': None, 
            'id': 10, 
            'order_id': '10', 
            'order_product_id': 10, 
            'price': 10, 
            'private_comment': None, 
            'product': None, 
            'product_id': '0010', 
            'public_comment': None, 
            'quantity': 100, 
            'status': None, 
            'subcustomer': None
        })
        res = self.client.get('/api/v1/admin/order/10')
        self.assertTrue(res.json[0]['total_krw'], 1010)

    def test_set_order_product_status(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/order_product/10/status/0'))

    def test_get_order_product_status_history(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/order_product/10/status/history'))
        res = self.client.get('/api/v1/admin/order_product/10/status/history')
        self.assertEqual(res.json, [{
            'set_at': '2020-01-01 01:00:00',
            'set_by': 'user1',
            'status': 'Pending'
        }])
        res = self.client.get('/api/v1/admin/order_product/30/status/history')
        self.assertEqual(res.status_code, 404)

    def test_get_product(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/product'))

    def test_save_product(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/product', json={
                'name': 'Product1',
                'name_english': '', 
                'name_russian': ''
            }))

    def test_delete_product(self):
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/product/0'))

    def test_get_transactions(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/transaction'))

    def test_save_transaction(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/transaction'))

    def test_delete_user(self):
        self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/user/10'))
        res = self.client.delete('/api/v1/admin/user/20')
        self.assertEqual(res.status_code, 409)

    def test_save_user(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/user'))
