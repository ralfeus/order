from unittest.mock import patch
from app.models.address import Address
from datetime import datetime

from app.users.models.role import Role
from app.users.models.user import User
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.order_status import OrderStatus
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.purchase.models import PurchaseOrder
from app.purchase.models.company import Company

from tests import BaseTestCase, db

class TestPurchaseOrdersApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        po_admin_role = Role(name='po-admin')
        self.user = User(username='user1_test_po_api', email='root_test_po_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_po_api', email='root_test_po_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role, po_admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role, po_admin_role,
            Product(id='0000', name='Test product', price=10, weight=10)
        ])

    def test_get_purchase_orders(self):
        order = Order()
        suborder = Suborder(order=order)
        po = PurchaseOrder(suborder=suborder, company=Company(name='Test'))
        self.try_add_entities([
            order, suborder, po,
        ])

        self.try_admin_operation(
            lambda: self.client.get(f"/api/v1/admin/purchase/order/{po.id}")
        )

    def test_search_purchase_order_by_subcustomer(self):
        subcustomer = Subcustomer(name='Test')
        order = Order()
        suborder = Suborder(order=order, subcustomer=subcustomer)
        po = PurchaseOrder(suborder=suborder, company=Company(name='Test'))
        self.try_add_entities([
            order, suborder, po,
        ])
        res = self.try_admin_operation(
            lambda: self.client.get("/api/v1/admin/purchase/order?draw=2&columns%5B0%5D%5Bdata%5D=customer.name&columns%5B0%5D%5Bname%5D=&columns%5B0%5D%5Bsearch%5D%5Bvalue%5D={}&search%5Bvalue%5D=".format(
                                    subcustomer.name))
        )
        self.assertEqual(res.status_code, 200)
    
    def test_get_vendors(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/purchase/vendor')
        )
        self.assertEqual(len(res.json), 1)

    @patch('app.purchase.jobs.post_purchase_orders')
    def test_create_purchase_order(self, po_mock):
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
            Company(id=gen_int_id, address_id=gen_int_id)
        ])
        res = self.try_admin_operation(lambda: 
            self.client.post('/api/v1/admin/purchase/order', json={
                'order_id': gen_id,
                'company_id': gen_int_id,
                'address_id': gen_int_id,
                'vendor': 'AtomyQuick',
                'contact_phone': '000-0000-0000'
            })
        )
        self.assertEqual(res.status_code, 202)
        self.assertEqual(PurchaseOrder.query.count(), 2)

    @patch('app.purchase.jobs.post_purchase_orders')
    def test_create_existing_po(self, po_mock):
        po_mock.return_value = None
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_int_id = int(datetime.now().timestamp())
        order = Order(id=f'ORD-{gen_id}', user=self.user, status=OrderStatus.can_be_paid)
        subcustomer = Subcustomer(id=gen_int_id)
        suborder = Suborder(id=f'SOS-{gen_id}-1', order_id=f'ORD-{gen_id}', 
                            subcustomer_id=gen_int_id)
        self.try_add_entities([
            order,
            subcustomer,
            suborder,
            OrderProduct(suborder_id=f'SOS-{gen_id}-1', product_id='0000', quantity=1),
            Address(id=gen_int_id, zip='00000'),
            Company(id=gen_int_id, address_id=gen_int_id),
            PurchaseOrder(suborder=suborder)
        ])
        res = self.try_admin_operation(lambda: 
            self.client.post('/api/v1/admin/purchase/order', json={
                'order_id': f'ORD-{gen_id}',
                'company_id': gen_int_id,
                'address_id': gen_int_id,
                'vendor': 'AtomyQuick',
                'contact_phone': '000-0000-0000'
            })
        )
        self.assertEqual(res.json['status'], 409)

    def test_validate_order_subcustomers(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        gen_int_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Order(id=gen_id, user=self.user, status=OrderStatus.can_be_paid),
            Order(id=gen_id + '2', user=self.user, status=OrderStatus.can_be_paid),
            Subcustomer(id=gen_int_id, username='test', password='test'),
            Subcustomer(id=gen_int_id + 1, username='test1', password='test1'),
            Subcustomer(id=gen_int_id + 2, username='23426444', password='atomy#01'),
            Suborder(id=gen_id, order_id=gen_id, subcustomer_id=gen_int_id),
            Suborder(id=gen_id + '1', order_id=gen_id, subcustomer_id=gen_int_id + 1),
            Suborder(id=gen_id+ '2', order_id=gen_id + '2', subcustomer_id=gen_int_id + 2),
            OrderProduct(suborder_id=gen_id, product_id='0000'),
            OrderProduct(suborder_id=gen_id + '1', product_id='0000'),
            Address(id=gen_int_id, zip='00000'),
            Company(id=gen_int_id, address_id=gen_int_id)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/purchase/order/validate',
                json={
                    'address_id': None,
                    'company_id': None,
                    'contact_phone': None,
                    'order_id': gen_id,
                    'vendor':  None
        }))
        self.assertEqual(res.json['status'], 'error')
        self.assertIn('test,test1', res.json['message'])
        res = self.client.post('/api/v1/admin/purchase/order/validate',
            json={
                'address_id': None,
                'company_id': None,
                'contact_phone': None,
                'order_id': gen_id + '2',
                'vendor':  None
        })
        self.assertEqual(res.get_json()['status'], 'success')

    # def test_create_po_alternative_address(self):
    #     gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
    #     gen_int_id = int(datetime.now().timestamp())
    #     self.try_add_entities([
    #         Order(id=gen_id, user=self.user, status=OrderStatus.can_be_paid),
    #         Subcustomer(id=gen_int_id),
    #         Subcustomer(id=gen_int_id + 1),
    #         Suborder(id=gen_id, order_id=gen_id, subcustomer_id=gen_int_id),
    #         Suborder(id=gen_id + '1', order_id=gen_id, subcustomer_id=gen_int_id + 1),
    #         OrderProduct(suborder_id=gen_id, product_id='0000'),
    #         OrderProduct(suborder_id=gen_id + '1', product_id='0000'),
    #         Address(id=gen_int_id, zip='00000'),
    #         Address(id=gen_int_id + 1, zip='11111'),
    #         Company(id=gen_int_id, address_id=gen_int_id)
    #     ])
    #     self.try_admin_operation(lambda: self.client.post('/api/v1/admin/purchase/order',
    #         json={
    #             'order_id': gen_id,
    #             'company_id': gen_int_id,
    #             'address_id': gen_int_id + 1,
    #             'contact_phone': '111-1111-1111',
    #             'vendor': 'AtomyQuick'
    #     }))
    #     po = PurchaseOrder.query.all()[0]
    #     self.assertEqual(po.address.zip, '11111')
