from datetime import datetime

from tests import BaseTestCase, db

from app.currencies.models import Currency
from app.orders.models import Order
from app.products.models import Product
from app.payments.models import Transaction, TransactionStatus
from app.models import Country, Role, Shipping, ShippingRate, User

class TestAdminApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None

        db.create_all()
        admin_role = Role(id=10, name='admin')
        self.admin = User(id=0, username='root', email='user@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.user = User(id=10, username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True)
        self.try_add_entities([
            admin_role, self.user, self.admin,
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

    def test_delete_user(self):
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/user/20'))
        self.assertEqual(res.status_code, 409)

    def test_save_user(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/user/0'))
        self.assertEqual(res.status_code, 400)
