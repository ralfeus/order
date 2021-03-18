from datetime import datetime

from app.users.models.role import Role
from app.users.models.user import User
from app.orders.models import Order, Suborder
from app.products.models import Product
from app.purchase.models import PurchaseOrder

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