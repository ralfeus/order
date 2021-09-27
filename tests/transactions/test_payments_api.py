from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models.currency import Currency
from app.orders.models.order import Order, OrderStatus
from app.payments.models.payment import Payment, PaymentStatus
from app.payments.models.payment_method import PaymentMethod
from app.purchase.models.company import Company
from app.models.address import Address
from app.users.models.role import Role
from app.users.models.user import User

class TestPaymentApi(BaseTestCase):
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
            lambda: self.client.post('/api/v1/payment', json={
                'orders': [gen_id],
                'sender_name': 'Test',
                'amount_sent_original': 100,
                'currency_code': 'USD',
                'payment_method': {'id': gen_id_int}
            }))
        self.assertEqual(Payment.query.count(), 1)
        transaction = Payment.query.first()
        self.assertEqual(transaction.amount_sent_krw, 100)

    def test_get_payments(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/payment'))

    def test_save_payment(self):
        gen_id_int = datetime.now().microsecond
        self.try_add_entities([
            Currency(code='USD', name='US Dollar', rate=1),
            Address(id=gen_id_int),
            Company(id=gen_id_int, address_id=gen_id_int),
            PaymentMethod(id=gen_id_int, payee_id=gen_id_int),
            Payment(id=0, user=self.user, currency_code='USD',
                    status=PaymentStatus.pending, payment_method_id=gen_id_int)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/payment/0', json={
                'user_id': self.user.id,
                'amount_received_krw': 100,
                'sender_name': 'Test',
                'payment_method': {'id': gen_id_int},
                'currency_code': 'USD'
        }))
        self.assertEqual(res.json['data'][0]['amount_received_krw'], 100)

    def test_approve_payment_no_received_krw(self):
        currency = Currency(code='KRW', rate=1)
        transaction = Payment(amount_sent_original=100, currency=currency,
            user=self.user, status=PaymentStatus.pending)
        self.try_add_entities([currency, transaction])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/payment/{transaction.id}', json={
                'status': 'approved'
        }))
        self.assertIsNotNone(res.json.get('error'))
    
    def test_pay_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        currency = Currency(code='KRW', rate=1)
        order = Order(id=gen_id, total_krw=90, user=self.user,
                      status=OrderStatus.pending)
        payment = Payment(amount_sent_original=100, currency=currency,
            amount_received_krw=100,
            user=self.user, status=PaymentStatus.pending,
            orders=[order])
        self.try_add_entities([order, payment, currency])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/payment/{payment.id}', json={
                'status': 'approved'
            }))
        self.assertIsNone(res.json.get('error'))
        order = Order.query.get(gen_id)
        self.assertEqual(order.status, OrderStatus.can_be_paid)

    def test_pay_po_created_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        currency = Currency(code='KRW', rate=1)
        order = Order(id=gen_id, total_krw=90, user=self.user,
                      status=OrderStatus.po_created)
        payment = Payment(amount_sent_original=100, currency=currency,
            amount_received_krw=100,
            user=self.user, status=PaymentStatus.pending,
            orders=[order])
        self.try_add_entities([order, payment, currency])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/payment/{payment.id}', json={
                'status': 'approved'
            }))
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(gen_id)
        self.assertEqual(order.status, OrderStatus.po_created)

    def test_get_payment_methods(self):
        self.try_add_entities([
            PaymentMethod(name='Payment method 1')
        ])
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/payment/method'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]['name'], 'Payment method 1')


    def test_create_payment_method(self):
        self.try_add_entities([Company(id=1, name='Company 1')])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/payment/method', json={
                'name': 'Payment method 1',
                'payee_id': 1
            })
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PaymentMethod.query.count(), 1)
    
    def test_modify_payment_method(self):
        self.try_add_entities([
            Company(id=1, name='Company 1'),
            PaymentMethod(id=1, name='Payment method 1', payee_id=1)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/payment/method/1', json={
                'instructions': 'Instructions 1'
            })
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PaymentMethod.query.count(), 1)
        self.assertEqual(PaymentMethod.query.first().instructions, 'Instructions 1')

    def test_delete_payment_method(self):
        self.try_add_entities([
            Company(id=1, name='Company 1'),
            PaymentMethod(id=1, name='Payment method 1', payee_id=1)
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/payment/method/1')
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PaymentMethod.query.count(), 0)
