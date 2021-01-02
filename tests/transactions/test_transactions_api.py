from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models.currency import Currency
from app.orders.models.order import Order, OrderStatus
from app.orders.models.order_product import OrderProduct
from app.orders.models.suborder import Suborder
from app.payments.models.payment import Payment, Transaction
from app.purchase.models.company import Company
from app.products.models.product import Product
from app.shipping.models.shipping import Shipping, ShippingRate
from app.models.country import Country
from app.models.address import Address
from app.models.role import Role
from app.models.user import User

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

    def test_create_payment_transaction(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_id_int = datetime.now().microsecond
        self.try_add_entities([
            Order(id=gen_id, user=self.user),
            Currency(code='USD', name='US Dollar', rate=1),
            Address(id=gen_id_int),
            Company(id=gen_id_int, address_id=gen_id_int),
            # PaymentMethod(id=gen_id_int, payee_id=gen_id_int),
            Payment(id=gen_id_int, user=self.user, currency_code='USD',
                amount_sent_krw=2600, amount_received_krw=2600)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/payment/{gen_id_int}', json={
                'status': 'approved'
            }))
        self.assertEqual(res.status_code, 200)
        transaction = Transaction.query.first()
        self.assertEqual(transaction.amount, 2600)
        self.assertEqual(self.user.balance, 2600)

    def test_create_pay_order_transaction(self):
        self.user.balance = 2600
        self.try_add_entities([
            Country(id='c1', name='country1'),
            Currency(code='USD', rate=0.5),
            Currency(code='RUR', rate=0.5),
            Product(id='0000', name='Test product', price=10, weight=10),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=100),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=200)
        ])
        order = Order(
            user=self.user, status=OrderStatus.pending)
        suborder = Suborder(order=order)
        self.try_add_entities([
            order, suborder,
            OrderProduct(suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/{order.id}', json={
                'status': 'shipped'
            })
        )
        self.assertEqual(res.status_code, 200)
        transaction = Transaction.query.first()
        self.assertEqual(transaction.amount, -2600)
        self.assertEqual(self.user.balance, 0)

    def test_get_transactions(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/payment/transaction'))
