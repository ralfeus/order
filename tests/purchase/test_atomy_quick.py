from app.purchase.models.vendor_manager import PurchaseOrderVendorManager

from tests import BaseTestCase, db

class TestPurchaseOrdersVendorAtomyQuick(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

    def test_create_atomy_quick_instance(self):
        PurchaseOrderVendorManager.get_vendor('AtomyQuick')
