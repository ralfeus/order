'''
Tests of order products functionality API
'''
from datetime import datetime

from tests import BaseTestCase, db
from app.models import Country
from app.currencies.models import Currency
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.orders.models.order_product import OrderProduct, OrderProductStatus, \
    OrderProductStatusEntry
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.shipping.models import PostponeShipping, Shipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User

class TestOrderProductsApi(BaseTestCase):
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
            admin_role, self.user, self.admin,
            Currency(code='USD', rate=0.5),
            Currency(code='RUR', rate=0.5)
        ])

    def test_cancel_order_product(self):
        self.try_add_entities([
            Product(id='0000', name='Test product', price=10, weight=10),
            Product(id='0001', name='Test product 1', price=10, weight=10),
            Country(id='c1', name='country1'),
            Shipping(id=1, name='Shipping1'),
            PostponeShipping(),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=100),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=200),
        ])
        op_id = datetime.now().microsecond
        order = Order(user=self.user, shipping_method_id=1, country_id='c1')
        suborder = Suborder(order=order)
        op1 = OrderProduct(suborder=suborder, product_id='0000', quantity=75,
            price=10, status=OrderProductStatus.pending)
        op2 = OrderProduct(id=op_id, suborder=suborder, product_id='0001',
            quantity=10, price=10, status=OrderProductStatus.pending)
        self.try_add_entities([
            Product(id='0001', name='Test product 1', price=10, weight=100)
        ])
        self.try_add_entities([
            order, suborder,
            op1, op2
        ])
        res = self.try_user_operation(
            lambda: self.client.delete(f'/api/v1/order/product/{op_id}')
        )
        self.assertEqual(res.status_code, 200)
        op = OrderProduct.query.get(op_id)
        self.assertEqual(op, None)
        
    def test_postpone_order_product(self):
        op_id = datetime.now().microsecond
        self.try_add_entities([
            Product(id='0000', name='Test product', price=10, weight=10),
            Product(id='0001', name='Test product 1', price=10, weight=10),
            Country(id='c1', name='country1'),
            Shipping(id=1, name='Shipping1'),
            PostponeShipping(),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=100),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=200),
        ])
        order1 = Order(user=self.user, shipping_method_id=1, country_id='c1')
        self.try_add_entity(order1)
        order2 = Order(user=self.user, shipping_method_id=1, country_id='c1')
        self.try_add_entity(order2)
        suborder = Suborder(order=order1, subcustomer=Subcustomer())
        suborder1 = Suborder(order=order2, subcustomer=Subcustomer())
        self.try_add_entities([
            OrderProduct(suborder=suborder, product_id='0000', quantity=1),
            OrderProduct(id=op_id, suborder=suborder, product_id='0001', quantity=1),
            OrderProduct(id=op_id + 1, suborder=suborder1, product_id='0001', quantity=1)
        ])
        res = self.try_user_operation(
            lambda: self.client.post(f'/api/v1/order/product/{op_id}/postpone')
        )
        self.assertEqual(res.status_code, 200)
        orders = Order.query.all()
        self.assertEqual(len(orders), 3)
        self.assertEqual(orders[0].total_krw, 2610)
        self.assertEqual(orders[2].total_krw, 2510)
        self.client.post(f'/api/v1/order/product/{op_id + 1}/postpone')
        orders = Order.query.all()
        self.assertEqual(len(orders), 3)
        self.assertEqual(orders[0].total_krw, 2610)
        self.assertEqual(orders[2].total_krw, 5020)

    def test_set_order_product_status(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        op_id = datetime.now().microsecond
        order = Order(id=gen_id, user=self.user)
        self.try_add_entities([
            Product(id='0000', name='Test product', price=10, weight=10)
        ])
        self.try_add_entities([
            order,
            Suborder(id=op_id, order=order),
            OrderProduct(id=op_id, suborder_id=op_id, product_id='0000',
                price=10, quantity=10)
        ])
        self.try_user_operation(
            lambda: self.client.post(f'/api/v1/admin/order/product/{op_id}/status/pending'))

    def test_set_order_product_unavailable(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        op_id = datetime.now().microsecond
        order = Order(id=gen_id, user=self.user)
        self.try_add_entities([
            Product(id='0000', name='Test product', price=10, weight=10),
            Product(id='0001', name='Test product 1', price=10, weight=10)
        ])
        self.try_add_entities([
            order,
            Suborder(id=op_id, order=order),
            OrderProduct(id=op_id, suborder_id=op_id, product_id='0000',
                price=10, quantity=10),
            OrderProduct(id=op_id + 1, suborder_id=op_id, product_id='0001',
                price=10, quantity=1)
        ])
        self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/product/{op_id + 1}/status/unavailable'))
        order = Order.query.get(gen_id)
        self.assertEqual(order.subtotal_krw, 2600)
