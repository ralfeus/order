from app.purchase.models.vendor_manager import PurchaseOrderVendorManager

from tests import BaseTestCase, app, db

class TestPurchaseOrdersVendorAtomyQuick(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

    def test_create_atomy_quick_instance(self):
        PurchaseOrderVendorManager.get_vendor('AtomyQuick')

class TestPurchaseOrdersVendorAtomyCenter(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

    def test_create_atomy_center_instance(self):
        app.config['ATOMY_CENTER'] = True
        PurchaseOrderVendorManager.get_vendor('AtomyCenter')

    def test_create_atomy_center_disabled(self):
        app.config['ATOMY_CENTER'] = False
        with self.assertRaises(Exception):
            PurchaseOrderVendorManager.get_vendor('AtomyCenter')
