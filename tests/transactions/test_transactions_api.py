from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.orders.models import Order, OrderStatus
from app.payments.models import PaymentMethod, Transaction, TransactionStatus
from app.purchase.models import Company
from app.models import Address, Role, User

class TestTransactionApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user-' + str(__name__), email='user@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='admin-' + str(__name__), email='admin@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.admin, self.user, admin_role
        ])

    def test_create_payment(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_id_int = datetime.now().microsecond
        self.try_add_entities([
            Order(id=gen_id, user=self.user),
            Currency(code='USD', name='US Dollar', rate=1),
            Address(id=gen_id_int),
            Company(id=gen_id_int, address_id=gen_id_int),
            PaymentMethod(id=gen_id_int, payee_id=gen_id_int)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/transaction', json={
                'orders': [gen_id],
                'amount_original': 100,
                'currency_code': 'USD',
                'payment_method': gen_id_int
            }))
        self.assertEqual(Transaction.query.count(), 1)
        transaction = Transaction.query.first()
        self.assertEqual(transaction.amount_sent_krw, 100)

    def test_get_payments(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/transaction'))

    def test_save_payment(self):
        self.try_add_entities([
            Currency(code='USD', name='US Dollar', rate=1),
            Transaction(id=0, user=self.user, currency_code='USD',
                        status=TransactionStatus.pending)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/transaction/0', json={
                'amount_received_krw': 100
        }))
        self.assertEqual(res.json['transaction']['amount_received_krw'], 100)

    def test_approve_transaction_no_received_krw(self):
        currency = Currency(code='KRW', rate=1)
        transaction = Transaction(amount_sent_original=100, currency=currency,
                                  user=self.user, status=TransactionStatus.pending)
        self.try_add_entities([currency, transaction])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/transaction/{transaction.id}', json={
                'status': 'approved'
        }))
        self.assertEqual(res.status_code, 400)     
    
    def test_pay_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        currency = Currency(code='KRW', rate=1)
        order = Order(id=gen_id, total_krw=90, user=self.user,
                      status=OrderStatus.pending)
        transaction = Transaction(amount_sent_original=100, currency=currency,
                                  amount_received_krw=100,
                                  user=self.user, status=TransactionStatus.pending,
                                  orders=[order])
        self.try_add_entities([ order, transaction, currency ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/transaction/{transaction.id}', json={
                'status': 'approved'
            }))
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(gen_id)
        self.assertEqual(order.status, OrderStatus.paid)

    def test_get_payment_methods(self):
        self.try_add_entities([
            PaymentMethod(name='Payment method 1')
        ])
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/transaction/method'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]['name'], 'Payment method 1')
