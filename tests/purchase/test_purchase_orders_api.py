from app.models.address import Address
from datetime import datetime

from app.users.models.role import Role
from app.users.models.user import User
from app.orders.models import Order, OrderProduct, OrderStatus, Subcustomer, Suborder
from app.products.models import Product
from app.purchase.models import PurchaseOrder
from app.purchase.models.company import Company

from tests import BaseTestCase, db

class TestPurchaseOrdersApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_po_api', email='root_test_po_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_po_api', email='root_test_po_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Product(id='0000', name='Test product', price=10, weight=10)
        ])

    def test_get_purchase_orders(self):
        order = Order()
        suborder = Suborder(order=order)
        po = PurchaseOrder(suborder=suborder)
        self.try_add_entities([
            order, suborder, po,
        ])

        self.try_admin_operation(
            lambda: self.client.get(f"/api/v1/admin/purchase/order/{po.id}")
        )
    
    def test_get_vendors(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/purchase/vendor')
        )
        self.assertEqual(len(res.json), 2)

    def test_create_purchase_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_int_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Order(id=gen_id, user=self.user, status=OrderStatus.can_be_paid),
            Subcustomer(id=gen_int_id),
            Subcustomer(id=gen_int_id + 1),
            Suborder(id=gen_id, order_id=gen_id, subcustomer_id=gen_int_id),
            Suborder(id=gen_id + '1', order_id=gen_id, subcustomer_id=gen_int_id + 1),
            OrderProduct(suborder_id=gen_id, product_id='0000'),
            OrderProduct(suborder_id=gen_id + '1', product_id='0000'),
            Address(id=gen_int_id, zip='00000'),
            Company(id=gen_int_id, address_id=gen_int_id)
        ])

        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/purchase/order', json={
                'order_id': gen_id,
                'company_id': gen_int_id,
                'vendor': 'AtomyCenter',
                'contact_phone': '1-1-1'
            })
        )
