from datetime import datetime

from tests import BaseTestCase, db
from app.models import Country, Currency, Product, Role, Shipping, ShippingRate, User
from app.orders.models import Order, OrderProduct

class TestProductsApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_orders_api', email='root_test_orders_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_orders_api', email='root_test_orders_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='RUR', rate=0.5),
            Country(id='c1', name='country1'),
            Product(id='0000', name='Test product', price=10, weight=10)
        ])

    def test_get_products(self):
        res = self.client.get('/api/v1/product')
        self.assertEqual(res.json, [
            {
                'available': False,
                'id': '0000',
                'name': 'Test product',
                'name_english': None,
                'name_russian': None,
                'points': None,
                'price': 10,
                'weight': 10
            }
        ])
        res = self.client.get('/api/v1/product/0000')
        self.assertEqual(len(res.json), 1)
        res = self.client.get('/api/v1/product/0')
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]['id'], '0000')
        res = self.client.get('/api/v1/product/999')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data, b'No product with code <999> was found')

    def test_search_product(self):
        self.try_add_entities([
            Product(id='0001', name='Korean name 1', name_english='English name', name_russian='Russian name', price=1, available=True)
        ])
        res = self.client.get('/api/v1/product/search/0001')
        self.assertEqual(res.json, [
            {
                'id': '0001',
                'name': 'Korean name 1',
                'name_english': 'English name',
                'name_russian': 'Russian name',
                'points': None,
                'price': 1,
                'weight': 0,
                'available': True
            }
        ])
