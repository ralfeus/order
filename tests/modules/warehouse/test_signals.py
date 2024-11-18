'''
Tests of warehouse signals handling
'''
from datetime import datetime

from tests import BaseTestCase, db
from app.models import Country
from app.currencies.models import Currency
from app.users.models import Role
from app.users.models import User
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.orders.models.order_product import OrderProduct, OrderProductStatus
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.modules.warehouse.models import OrderProductWarehouse, Warehouse, \
    WarehouseProduct
from app.shipping.models.shipping import Shipping, ShippingRate

class TestWarehouseApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_warehouse_api', email='root_test_warehouse_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_warehouse_api', email='root_test_warehouse_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role
        ])

    def test_get_order_product_from_warehouse(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_int_id = int(datetime.now().timestamp())
        self.try_add_entities(([
            Product(id='0001', name='Product 1', price=10, weight=10),
            Country(id='c1'),
            Currency(code='USD', rate=0.5),
            Currency(code='EUR', rate=0.5)
        ]))
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending, country_id='c1')
        suborder = Suborder(order=order)
        self.try_add_entities([
            order, suborder,
            OrderProduct(id=gen_int_id, suborder=suborder, product_id='0001', quantity=5, status=OrderProductStatus.purchased),
            Warehouse(id=gen_int_id, name='Test WH'),
            WarehouseProduct(warehouse_id=gen_int_id, product_id='0001', quantity=10),
            OrderProductWarehouse(order_product_id=gen_int_id, warehouse_id=gen_int_id),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=100)

        ])

        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/{gen_id}', json={
                "status": "shipped",
        }))
        self.assertEqual(res.status_code, 200)
        warehouse_product = WarehouseProduct.query.get((gen_int_id, '0001'))
        self.assertEqual(warehouse_product.quantity, 5)
