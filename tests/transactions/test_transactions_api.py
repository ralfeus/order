from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.orders.models import Order
from app.payments.models import PaymentMethod, Transaction, TransactionStatus
from app.models import Role, User

class TestTransactionApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user' + str(__class__), email='user@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='admin' + str(__class__), email='admin@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.admin, self.user, admin_role
        ])
    def test_get_transactions(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/transaction'))

    def test_save_transaction(self):
        self.try_add_entities([
            Transaction(id=0)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/transaction/0'))
    
    def test_pay_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        currency = Currency(code='KRW', rate=1)
        order = Order(id=gen_id, total_krw=90, user=self.user)
        transaction = Transaction(amount_sent_original=100, currency=currency, amount_received_krw=100,
                                  user=self.user, status=TransactionStatus.pending, orders=[order])
        self.try_add_entities([ order, transaction, currency ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/transaction/{transaction.id}', json={
                'status': 'approved'
            }))
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(gen_id)
        self.assertEqual(order.status, 'Paid')

    def test_get_payment_methods(self):
        self.try_add_entities([
            PaymentMethod(name='Payment method 1')
        ])
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/transaction/method'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]['name'], 'Payment method 1')
