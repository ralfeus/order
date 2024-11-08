from tests import BaseTestCase, db

from app.models import Country
from app.currencies.models import Currency
from app.shipping.models import DHL, Shipping, ShippingRate
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
                Country(id='c1', name='country1'),
                Currency(code='USD', name='US Dollar', rate=1),
                Currency(code='EUR', name='Euro', rate=1),
                Country(id='c2', name='country2'),
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
            {'id': 'c1', 'name': 'country1', 'sort_order': 999},
            {'id': 'c2', 'name': 'country2', 'sort_order': 999}
        ])

    def test_get_shipping(self):
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/shipping'))
        self.assertEqual(res.json, [
            {
                'id': 4,
                'name': 'DHL',
                'type': 'DHL',
                'enabled': True,
                'links': {'edit': '/admin/shipping/dhl/', 'print_label': ''},
                'is_consignable': False,
                'notification': None,
                'edit_url': '/admin/shipping/dhl/',
                'params': []
            },
            {
                'id': 1,
                'name': 'Shipping1',
                'type': '',
                'enabled': True,
                'links': {'edit': '', 'print_label': ''},
                'is_consignable': False,
                'notification': None,
                'edit_url': '',
                'params': []
            },
            {
                'id': 2,
                'name': 'Shipping2',
                'type': '',
                'enabled': True,
                'links': {'edit': '', 'print_label': ''},
                'is_consignable': False,
                'notification': None,
                'edit_url': '',
                'params': []
            },
            {
                'id': 3,
                'name': 'Shipping3',
                'type': '',
                'enabled': True,
                'links': {'edit': '', 'print_label': ''},
                'is_consignable': False,
                'notification': None,
                'edit_url': '',
                'params': []
            }
        ])
        res = self.client.get('/api/v1/shipping/c1')
        self.assertEqual(len(res.json), 2)
        res = self.client.get('/api/v1/shipping/c2/200')
        self.assertEqual(len(res.json), 2)
        res = self.client.get('/api/v1/shipping/c1/1000')
        self.assertEqual(res.status_code, 409)

    def test_get_shipping_rate(self):
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/shipping/rate/c2/2/200'))
        self.assertEqual(res.json['shipping_cost'], 150)
        res = self.client.get('/api/v1/shipping/rate/c2/200')
        self.assertEqual(res.json, {'2': 150, '3': 160})
