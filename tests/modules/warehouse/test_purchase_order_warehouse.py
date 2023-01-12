from unittest.mock import patch
from app.models.address import Address
from datetime import datetime

from app.users.models.role import Role
from app.users.models.user import User
from app.orders.models import Order, OrderProduct, OrderStatus, Subcustomer, Suborder
from app.products.models import Product
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from app.purchase.models.company import Company
from app.modules.warehouse.models import PurchaseOrderWarehouse, Warehouse, WarehouseProduct

from tests import BaseTestCase, db

class TestPurchaseOrdersWarehouse(BaseTestCase):
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
    
    @patch('app.purchase.jobs.post_purchase_orders')
    def test_create_purchase_order_for_warehouse(self, po_mock):
        po_mock.return_value = None
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_int_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Order(id=gen_id, user=self.user, status=OrderStatus.can_be_paid),
            Subcustomer(id=gen_int_id),
            Subcustomer(id=gen_int_id + 1),
            Suborder(id=gen_id, order_id=gen_id, subcustomer_id=gen_int_id),
            Suborder(id=gen_id + '1', order_id=gen_id, subcustomer_id=gen_int_id + 1),
            OrderProduct(suborder_id=gen_id, product_id='0000', quantity=1),
            OrderProduct(suborder_id=gen_id + '1', product_id='0000', quantity=1),
            Address(id=gen_int_id, zip='00000'),
            Company(id=gen_int_id, address_id=gen_int_id),
            Warehouse(id=gen_int_id)
        ])
        res = self.try_admin_operation(lambda: 
            self.client.post('/api/v1/admin/purchase/order', json={
                'order_id': gen_id,
                'company_id': gen_int_id,
                'address_id': gen_int_id,
                'vendor': 'AtomyQuick',
                'contact_phone': '000-0000-0000',
                'warehouse_id': gen_int_id
            })
        )
        self.assertEqual(res.status_code, 202)
        self.assertEqual(PurchaseOrder.query.count(), 2)
        self.assertEqual(PurchaseOrderWarehouse.query.count(), 2)

    def test_purchase_order_delivered(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_int_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Order(id=gen_id, user=self.user, status=OrderStatus.po_created),
            Subcustomer(id=gen_int_id + 1),
            Subcustomer(id=gen_int_id + 2)
        ])
        sos1 = Suborder(id=gen_id + '1', order_id=gen_id, subcustomer_id=gen_int_id + 1)
        sos2 = Suborder(id=gen_id + '2', order_id=gen_id, subcustomer_id=gen_int_id + 2)
        po1 = PurchaseOrder(id=gen_id + '1', suborder=sos1, company_id=gen_int_id,
            status=PurchaseOrderStatus.pending)
        po2 = PurchaseOrder(id=gen_id + '2', suborder=sos2, company_id=gen_int_id,
            status=PurchaseOrderStatus.pending)
        self.try_add_entities([
            sos1, sos2
        ])
        self.try_add_entities([
            OrderProduct(suborder_id=gen_id + '1', product_id='0000', quantity=1),
            OrderProduct(suborder_id=gen_id + '2', product_id='0000', quantity=1),
            Address(id=gen_int_id, zip='00000'),
            Company(id=gen_int_id, address_id=gen_int_id),
            Warehouse(id=gen_int_id),
            po1, po2,
            PurchaseOrderWarehouse(purchase_order_id=po1.id, warehouse_id=gen_int_id),
            PurchaseOrderWarehouse(purchase_order_id=po2.id, warehouse_id=gen_int_id)
        ])
        # Test deliver one PO. Should add one product to the warehouse
        res = self.try_admin_operation(lambda:
            self.client.post(f'/api/v1/admin/purchase/order/{po1.id}', json={
                'status': 'delivered'
            })
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(WarehouseProduct.query.count(), 1)
        self.assertEqual(WarehouseProduct.query.first().product_id, '0000')
        self.assertEqual(WarehouseProduct.query.first().quantity, 1)
        self.assertEqual(Order.query.first().status, OrderStatus.po_created)
        # Test deliver second PO. Should add one more product to warehouse
        # and mark sale order as at_warehouse
        res = self.client.post(f'/api/v1/admin/purchase/order/{po2.id}', json={
            'status': 'delivered'
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(WarehouseProduct.query.count(), 1)
        self.assertEqual(WarehouseProduct.query.first().product_id, '0000')
        self.assertEqual(WarehouseProduct.query.first().quantity, 2)
        self.assertEqual(Order.query.first().status, OrderStatus.at_warehouse)
