from datetime import datetime

from app.models import Role, User
from app.currencies.models import Currency
from tests import BaseTestCase, db

class TestCurrencyClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(id=10, name='admin')
        self.try_add_entities([
            User(username='root_test_currency_api', email='root_test_currency_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
                enabled=True, roles=[admin_role]),
            User(id=10, username='user1_test_currency_api', email='user_test_currency_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            admin_role
        ])

    def try_admin_operation(self, operation):
        '''
        Superseeds base method to add class-specific user and admin credentials
        '''
        return super().try_admin_operation(
            operation,
            'user1_test_currency_api', '1', 'root_test_currency_api', '1')

    def test_get_currencies(self):
        self.try_add_entities([
            Currency(code='0001', name='Currency_1', rate=1)
        ])
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/currency'))
        self.assertEqual(res.json[0], {
            'code': '0001',
            'name': 'Currency_1',
            'rate': 1.0
        })
    def test_save_currency(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Currency(code=gen_id, name='Currency_1', rate=1)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/currency/{gen_id}',
            json={'rate': 2})
        )
        self.assertEqual(res.status_code, 200)
        currency = Currency.query.get(gen_id)
        self.assertEqual(currency.rate, 2)

        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/currency/{gen_id}',
            json={'rate': '2@'})
        )
        self.assertEqual(res.status_code, 400)

    
    def test_delete_currency(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Currency(code=gen_id, name='Currency_1', rate=1)
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f'/api/v1/admin/currency/{gen_id}')
        )
        self.assertEqual(res.status_code, 200)
        currency = Currency.query.get(gen_id)
        self.assertEqual(currency, None)
    