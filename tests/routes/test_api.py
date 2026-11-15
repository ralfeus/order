from tests import BaseTestCase, db

from app.models import Country
from app.currencies.models import Currency
from app.shipping.models.shipping import Shipping, ShippingRate
from app.shipping.methods.dhl.models.dhl import DHL
from app.users.models.user import User

class TestClientApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        self.user = User(id=100, username='user1', email='user@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        try:
            entities = [ self.user,
                Country(id='c1', name='country1', capital='c1', first_zip='0', locale='en-US', currency_code='USD'),
                Currency(code='USD', name='US Dollar', rate=1),
                Currency(code='EUR', name='Euro', rate=1),
                Country(id='c2', name='country2', capital='c2', first_zip='1', locale='en-US', currency_code='EUR'),
                Shipping(id=1, name='Shipping1'),
                Shipping(id=2, name='Shipping2'),
                Shipping(id=3, name='Shipping3'),
                DHL(),
                ShippingRate(id=1, shipping_method_id=1, destination='c1', weight=100, rate=100),
                ShippingRate(id=5, shipping_method_id=2, destination='c1', weight=200, rate=110),
                ShippingRate(id=2, shipping_method_id=2, destination='c2', weight=100, rate=100),
                ShippingRate(id=3, shipping_method_id=2, destination='c2', weight=1000, rate=150),
                ShippingRate(id=4, shipping_method_id=3, destination='c2', weight=2000, rate=160)
            ]
            db.session.add_all(entities)
            db.session.commit()
        except:
            db.session.rollback()
        # login(self.client, 'user1', '1')

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_countries(self):
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/country'))
        self.assertEqual(res.json, [
            {'id': 'c1', 'name': 'country1', 'sort_order': 999, 'capital': 'c1', 'first_zip': '0', 'locale': 'en-US', 'currency_code': 'USD'},
            {'id': 'c2', 'name': 'country2', 'sort_order': 999, 'capital': 'c2', 'first_zip': '1', 'locale': 'en-US', 'currency_code': 'EUR'}
        ])

    def test_get_shipping(self):
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/shipping'))
        data = res.json
        # All 4 enabled methods returned; no country/weight given so all are available
        self.assertEqual(len(data), 4)
        self.assertTrue(all(m['disabled_reason'] is None for m in data))
        names = [m['name'] for m in data]
        self.assertIn('DHL', names)
        self.assertIn('Shipping1', names)

        # With country only: all methods returned, unavailable ones have disabled_reason
        res = self.client.get('/api/v1/shipping/c1')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertEqual(len(data), 4)
        available = [m for m in data if m['disabled_reason'] is None]
        self.assertEqual(len(available), 2)

        # With country + weight: methods without a rate have disabled_reason set
        res = self.client.get('/api/v1/shipping/c2/200')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertEqual(len(data), 4)
        available = [m for m in data if m['disabled_reason'] is None]
        self.assertEqual(len(available), 2)

        # Weight beyond all rates: all methods disabled, but still 200 with disabled_reason
        res = self.client.get('/api/v1/shipping/c1/1000')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertTrue(all(m['disabled_reason'] is not None for m in data))

    def test_get_shipping_rate(self):
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/shipping/rate/c2/2/200'))
        self.assertEqual(res.json['shipping_cost'], 150)
        res = self.client.get('/api/v1/shipping/rate/c2/200')
        self.assertEqual(res.json, {'2': 150, '3': 160})
