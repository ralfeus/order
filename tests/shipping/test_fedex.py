from tests import BaseTestCase, db
from app.currencies.models.currency import Currency
from app.models.address import Address
from app.models.country import Country
from app.users.models.role import Role
from app.users.models.user import User
from app.orders.models.order import Order
from app.shipping.methods.fedex.models.fedex import Fedex
from app.shipping.models.box import default_box
from app.shipping.models.shipping_contact import ShippingContact
from app.shipping.models.shipping_item import ShippingItem
from exceptions import ShippingException

class TestShippingFedex(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_fedex_api',
            email='root_test_fedex_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True)
        self.admin = User(username='root_test_fedex_api',
            email='root_test_fedex_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Country(id='ua', name='Ukraine', sort_order=0),
            Country(id='cz', name='Czech Republic', first_zip='100 00', capital="Prague"),
            Country(id='de', name='Germany', capital='Berlin', first_zip='01067'),
            Currency(code='USD', rate=1)
        ])

    def test_get_rate(self):
        fedex = Fedex()
        res = fedex.get_shipping_cost('cz')
        self.assertEqual(res, 198)
        res = fedex.get_shipping_cost('de')
        self.assertIsNotNone(res)

    def test_create_shipment(self):
        fedex = Fedex()
        sender = Address(name='Home', zip='01000', address_1_eng='Test', 
                         city_eng='Seoul', country_id='kr')
        sender_contact = ShippingContact(name='Test name', phone='010-1111-2222')
        recipient = Address(name='Dest', zip='100 00', address_1_eng='Test', 
                         city_eng='Prague', country_id='cz')
        recipient_contact = ShippingContact(name='Test recipient', phone='777 666 111')
        items = [
            ShippingItem('Item1', 1, 10, 10),
            ShippingItem('Item2', 2, 20, 20)
        ]
        default_box.weight = 1500
        res = fedex.consign(sender, sender_contact, recipient, recipient_contact, 
                            items, [default_box])
        self.assertIsNotNone(res.tracking_id)

    def test_is_shippable(self):
        fedex = Fedex()
        germany = Country.query.get('de')
        res = fedex.can_ship(germany, 1, [])
        assert res

    def test_print_label(self):
        fedex = Fedex()
        sender = Address(name='Home', zip='01000', address_1_eng='Test', 
                         city_eng='Seoul', country_id='kr')
        sender_contact = ShippingContact(name='Test name', phone='010-1111-2222')
        recipient = Address(name='Dest', zip='100 00', address_1_eng='Test', 
                         city_eng='Prague', country_id='cz')
        recipient_contact = ShippingContact(name='Test recipient', phone='777 666 111')
        items = [
            ShippingItem('Item1', 1, 10, 10),
            ShippingItem('Item2', 2, 20, 20)
        ]
        default_box.weight = 1500
        res = fedex.consign(sender, sender_contact, recipient, recipient_contact, 
                            items, [default_box])
        self.assertIsNotNone(res.tracking_id)

        self.try_add_entities([Order(id=1, user=self.user, tracking_id=res.tracking_id)])
        res = self.try_admin_operation(
            lambda: self.client.get('/admin/shipping/fedex/label?order_id=1'),
            admin_only=True)
        assert res.status_code == 200
