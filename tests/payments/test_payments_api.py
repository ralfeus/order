'''
Tests of sale order functionality API
'''
from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.users.models.role import Role
from app.users.models.user import User

class TestPaymentsApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_payments_api', email='root_test_payments_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_payments_api', email='root_test_payments_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='RUR', rate=0.5)
        ])

    def test_create_payment(self):
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/payment', json={
                "currency_code":"USD",
                'amount_sent_original': 100,
                'payment_method': {'id': 1}
        }))
        self.assertEqual(res.status_code, 200)
        res = self.client.post('/api/v1/payment', json={
                "currency_code":"EUR",
                'amount_sent_original': 100,
                'payment_method': {'id': 1}
        })
        self.assertIsNotNone(res.json['error'])
