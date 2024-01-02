from app.purchase.models.vendors.atomy_center import AtomyCenter
from exceptions import AtomyLoginError

from tests import BaseTestCase

class TestPurchaseOrdersVendorAtomyCenter(BaseTestCase):
    def test_login(self):
        center = AtomyCenter()
        username = 'atomy1026'
        password = '5714'
        center.login(username, password)

    def test_login_wrong(self):
        center = AtomyCenter()
        username = 'atomy1026'
        password = '5715'
        self.assertRaises(AtomyLoginError, lambda: center.login(username, password))