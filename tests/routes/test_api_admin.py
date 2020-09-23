from flask import Response
from datetime import datetime

from tests import BaseTestCase, db

from app.config import TestConfig
from app.invoices.models import Invoice
from app.orders.models import Order, OrderProduct, OrderProductStatusEntry, \
                              Suborder, Subcustomer
from app.products.models import Product
from app.models import Country, Currency,  \
    Role, Shipping, ShippingRate, Transaction, User

def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ))

def logout(client):
    return client.get('/logout')

class TestAdminApi(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        db.session.execute('pragma foreign_keys=on')

    def setUp(self):
        super().setUp()
        self.maxDiff = None

        db.create_all()
        admin_role = Role(id=10, name='admin')
        self.try_add_entities([
            admin_role,
            User(id=0, username='root', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True, roles=[admin_role]),
            User(id=10, username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            User(id=20, username='user2', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            Country(id='c1', name='country1'),
            Currency(code='RUR', rate=1),
            Currency(code='USD', rate=1),
            Product(id='0010', name='Test product'),
            Shipping(id=10, name='shipping1'),
            ShippingRate(id=10, shipping_method_id=10, destination='c1', weight=1000, rate=10),
            Order(id='test-api-admin-1', user_id=20, status='pending', country_id='c1',
                  shipping_method_id=10,
                  tracking_id='T00', tracking_url='https://tracking.fake/T00'),
            Order(id='test-api-admin-2', user_id=20, status='shipped', country_id='c1')
        ])

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def try_admin_operation(self, operation):
        return super().try_admin_operation(operation, 'user1', '1', 'root', '1')

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
        self.try_add_entities([
            Transaction(id=0)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/transaction/0'))

    def test_delete_user(self):
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/user/20'))
        self.assertEqual(res.status_code, 409)

    def test_save_user(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/user/0'))
        self.assertEqual(res.status_code, 400)
