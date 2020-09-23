from datetime import datetime
from flask import url_for
import unittest

from app import create_app, db
from app.config import TestConfig
import app.routes.api as test_target

app = create_app(TestConfig)
app.app_context().push()
from app.orders.models import Order, OrderProduct, OrderProductStatusEntry
from app.models import Country, Currency, \
    Product, Shipping, ShippingRate, User

def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ))

class TestClientApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # db.session.execute('pragma foreign_keys=on')
        pass

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        db.create_all()
        try:
            entities = [
                Country(id='c1', name='country1'),
                Currency(code='USD', name='US Dollar', rate=1),
                Currency(code='RUR', name='Russian rouble', rate=1),
                Country(id='c2', name='country2'),
                Shipping(id=1, name='Shipping1'),
                Shipping(id=2, name='Shipping2'),
                Shipping(id=3, name='Shipping3'),
                ShippingRate(id=1, shipping_method_id=1, destination='c1', weight=100, rate=100),
                ShippingRate(id=5, shipping_method_id=2, destination='c1', weight=200, rate=110),
                ShippingRate(id=2, shipping_method_id=2, destination='c2', weight=100, rate=100),
                ShippingRate(id=3, shipping_method_id=2, destination='c2', weight=1000, rate=150),
                ShippingRate(id=4, shipping_method_id=3, destination='c2', weight=2000, rate=160),
                Order(id='ORD-2020-00-0001', shipping_method_id=1),
                OrderProduct(id=1, order_id='ORD-2020-00-0001'),
                OrderProduct(id=2, order_id='ORD-2020-00-0001'),
                OrderProductStatusEntry(order_product_id=1, user_id=1, status="Pending", set_at=datetime(2020, 1, 1, 1, 0, 0)),
                OrderProductStatusEntry(order_product_id=2, user_id=1, status="Pending", set_at=datetime(2020, 1, 1, 1, 0, 0)),
                Product(id='0001', name='Korean name 1', name_english='English name', name_russian='Russian name', price=1, available=True),
                Product(id='0002', name='Korean name 2'),
                User(id=100, username='user1', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True)
            ]
            db.session.add_all(entities)
            db.session.commit()
        except:
            db.session.rollback()
        login(self.client, 'user1', '1')

    def tearDown(self):
        if self._ctx is not None:
            self._ctx.pop()
        db.session.remove()
        db.drop_all()

    def test_get_countries(self):
        res = self.client.get(url_for('api.get_countries'))
        self.assertEqual(res.json, [
            {'id': 'c1', 'name': 'country1'},
            {'id': 'c2', 'name': 'country2'}
        ])

    def test_get_currency_rate(self):
        res = test_target.get_currency_rate()
        self.assertEqual(res.json, {
            'USD': '1.00000',
            'RUR': '1.00000'
        })


    def test_get_shipping(self):
        res = self.client.get('/api/v1/shipping')
        self.assertEqual(res.json, [
            {'id': 1, 'name': 'Shipping1'},
            {'id': 2, 'name': 'Shipping2'},
            {'id': 3, 'name': 'Shipping3'}
        ])
        res = self.client.get('/api/v1/shipping/c1')
        self.assertEqual(len(res.json), 2)
        res = self.client.get('/api/v1/shipping/c2/200')
        self.assertEqual(len(res.json), 2)
        res = self.client.get('/api/v1/shipping/c1/1000')
        self.assertEqual(res.status_code, 409)

    def test_get_shipping_rate(self):
        res = self.client.get('/api/v1/shipping/rate/c2/2/200')
        self.assertEqual(res.json['shipping_cost'], 150)
        res = self.client.get('/api/v1/shipping/rate/c2/200')
        self.assertEqual(res.json, {'2': 150, '3': 160})

if __name__ == '__main__':
    unittest.main()
