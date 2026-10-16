'''
Tests of purchase orders creation for suborders of different product vendors
'''
from unittest.mock import patch

from app.models.address import Address
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.order_status import OrderStatus
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.purchase.models import PurchaseOrder
from app.purchase.models.company import Company
from app.purchase.models.vendors.atomy_quick import AtomyQuick
from app.purchase.po_manager import NoPurchaseOrderVendorError, create_purchase_orders, \
    get_default_vendor_id
from app.settings.models.setting import Setting
from app.users.models.role import Role
from app.users.models.user import User

from tests import BaseTestCase, db

PASSWORD_HASH = 'pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576'


class TestPurchaseOrderVendors(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        po_admin_role = Role(name='po-admin')
        self.admin = User(username='admin_po_vendors', email='a@name.com',
                          password_hash=PASSWORD_HASH, enabled=True, roles=[po_admin_role])
        self.address = Address(id=1, zip='00000')
        self.company = Company(id=1, address_id=1)
        self.order = Order(user=self.admin, status=OrderStatus.can_be_paid)
        self.try_add_entities([
            po_admin_role, self.admin, self.address, self.company, self.order,
            Product(id='0001', vendor='Atomy', name='Atomy 1', price=10, weight=10),
            Product(id='0001', vendor='AtomyAza', name='AZA 1', price=20, weight=10),
        ])
        subcustomer = Subcustomer(username='s1', password='p1')
        self.atomy_suborder = Suborder(order=self.order, subcustomer=subcustomer)
        self.try_add_entities([self.atomy_suborder])
        self.aza_suborder = Suborder(order=self.order, subcustomer=subcustomer)
        self.try_add_entities([self.aza_suborder])
        self.try_add_entities([
            OrderProduct(suborder=self.atomy_suborder, product_id='Atomy:0001', quantity=1),
            OrderProduct(suborder=self.aza_suborder, product_id='AtomyAza:0001', quantity=1),
        ])

    def _create(self, **kwargs):
        return create_purchase_orders(
            self.order, self.company, self.address, contact_phone='000-0000-0000', **kwargs)

    def _po_vendors(self):
        return {po.suborder.vendor: po.vendor for po in PurchaseOrder.query}

    def test_default_vendor(self):
        self.assertEqual(get_default_vendor_id('Atomy'), 'AtomyQuick')
        self.assertIsNone(get_default_vendor_id('AtomyAza'))
        self.try_add_entities([
            Setting(key='purchase.default_vendor.Atomy', value='AtomyCenter'),
            Setting(key='purchase.default_vendor.AtomyAza', value='AzaVendor'),
        ])
        self.assertEqual(get_default_vendor_id('Atomy'), 'AtomyCenter')
        self.assertEqual(get_default_vendor_id('AtomyAza'), 'AzaVendor')

    def test_vendor_per_product_vendor(self):
        pos = self._create(vendor=AtomyQuick(), vendors={'AtomyAza': 'AzaVendor'})
        self.assertEqual(len(pos), 2)
        self.assertEqual(self._po_vendors(), {'Atomy': 'AtomyQuick', 'AtomyAza': 'AzaVendor'})

    def test_vendors_map_overrides_legacy_vendor(self):
        self._create(vendor=AtomyQuick(),
                     vendors={'Atomy': 'AtomyCenter', 'AtomyAza': 'AzaVendor'})
        self.assertEqual(self._po_vendors(), {'Atomy': 'AtomyCenter', 'AtomyAza': 'AzaVendor'})

    def test_default_vendor_is_used(self):
        self.try_add_entities([Setting(key='purchase.default_vendor.AtomyAza', value='AzaVendor')])
        self._create()
        self.assertEqual(self._po_vendors(), {'Atomy': 'AtomyQuick', 'AtomyAza': 'AzaVendor'})

    def test_no_vendor_for_product_vendor(self):
        with self.assertRaises(NoPurchaseOrderVendorError) as ctx:
            self._create(vendor=AtomyQuick())
        self.assertIn('AtomyAza', str(ctx.exception))
        self.assertEqual(PurchaseOrder.query.count(), 0)

    def test_po_ids_keep_format(self):
        self._create(vendor=AtomyQuick(), vendors={'AtomyAza': 'AzaVendor'})
        self.assertEqual(
            sorted(po.id for po in PurchaseOrder.query),
            sorted('PO-' + s.id[4:] for s in (self.atomy_suborder, self.aza_suborder)))

    @patch('app.purchase.jobs.post_purchase_orders')
    def test_api_vendors(self, _po_mock):
        payload = {
            'order_id': self.order.id, 'company_id': 1, 'address_id': 1,
            'vendor': 'AtomyQuick', 'contact_phone': '000-0000-0000'
        }
        self.login(self.admin.username, '1')
        res = self.client.post('/api/v1/admin/purchase/order', json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn('AtomyAza', res.get_data(as_text=True))

        res = self.client.post('/api/v1/admin/purchase/order', json={
            **payload, 'vendors': {'AtomyAza': 'Nonexistent'}})
        self.assertEqual(res.status_code, 400)
        self.assertIn('Nonexistent', res.get_data(as_text=True))
        self.assertEqual(PurchaseOrder.query.count(), 0)

        res = self.client.post('/api/v1/admin/purchase/order', json={
            **payload, 'vendors': {'AtomyAza': 'AtomyQuick'}})
        self.assertEqual(res.status_code, 202)
        self.assertEqual(self._po_vendors(), {'Atomy': 'AtomyQuick', 'AtomyAza': 'AtomyQuick'})

    @patch('app.purchase.routes.api.atomy_login2')
    def test_validate_skips_non_atomy_suborders(self, login_mock):
        self.login(self.admin.username, '1')
        res = self.client.post('/api/v1/admin/purchase/order/validate',
                               json={'order_id': self.order.id})
        self.assertEqual(res.json['status'], 'success')
        self.assertEqual(login_mock.call_count, 1)
