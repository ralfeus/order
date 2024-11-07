from tests import BaseTestCase, db
from app.models.address import Address
from app.models.country import Country
from app.shipping.methods.fedex.models.fedex import Fedex
from app.shipping.models.box import default_box
from app.shipping.models.shipping_item import ShippingItem
from exceptions import ShippingException

class TestShippingFedex(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        # admin_role = Role(name='admin')
        # self.user = User(username='user1_test_ems_api',
        #     email='root_test_ems_api@name.com',
        #     password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
        #     enabled=True)
        # self.admin = User(username='root_test_ems_api',
        #     email='root_test_ems_api@name.com',
        #     password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
        #     enabled=True, roles=[admin_role])
        self.try_add_entities([
            # self.user, self.admin, admin_role,
            Country(id='ua', name='Ukraine', sort_order=0),
            Country(id='cz', name='Czech Republic', first_zip='10 000'),
            Country(id='de', name='Germany')
        ])

    def test_get_rate(self):
        fedex = Fedex(test_mode=True)
        res = fedex.get_shipping_cost('CZ')
        self.assertEqual(res, [{'weight': 4, 'rate': 101}])

    def test_create_shipment(self):
        fedex = Fedex(test_mode=True)
        sender = Address(name='Home', zip='01000', address_1_eng='Test', 
                         city_eng='Seoul', country_id='kr')
        sender_contact = {'name': 'Test name', 'phone': '010-1111-2222'}
        recipient = Address(name='Dest', zip='10000', address_1_eng='Test', 
                         city_eng='Prague', country_id='cz')
        recipient_contact = {'name': 'Test recipient', 'phone': '777 666 111'}
        items = [
            ShippingItem('Item1', 1, 10),
            ShippingItem('Item2', 2, 20)
        ]
        default_box.weight = 10
        try:
            res = fedex.consign(sender, sender_contact, recipient, recipient_contact, 
                                items, [default_box])
            self.assertIsNotNone(res.consignment_id)
        except ShippingException as e:
            print(e.message)
            self.assertTrue(False)