from datetime import datetime
from unittest.mock import patch
from tests import BaseTestCase, db
from app.models import Country
from app.models.address import Address
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.shipping.methods.ems.models import EMS
from app.shipping.models.box import Box
from app.shipping.models.shipping import Shipping
from app.shipping.models.shipping_contact import ShippingContact
from app.users.models import Role, User
from common.exceptions import OrderError

class TestShippingEMS(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_ems_api',
            email='root_test_ems_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True)
        self.admin = User(username='root_test_ems_api',
            email='root_test_ems_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Country(id='ua', name='Ukraine', sort_order=0),
            Country(id='cz', name='Czech Republic'),
            Country(id='de', name='Germany')
        ])


    def test_get_rate(self):
        ems = EMS()
        rate = ems.get_shipping_cost('ua', 100)
        self.assertIsInstance(rate, int)

    @patch('app.shipping.methods.ems.models.ems.EMS.print')
    def test_print_label(self, po_mock):
        po_mock.return_value = {}
        self.try_add_entity(EMS())
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending)
        order.shipping = db.session.get(Shipping, 1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/admin/shipping/ems/label?order_id={order.id}'))
        self.assertEqual(res.status_code, 200)
        order = db.session.get(Order, gen_id)
        self.assertEqual(order.status, OrderStatus.shipped)

    @patch('app.shipping.methods.ems.models.ems.EMS._EMS__create_new_consignment')
    @patch('app.shipping.methods.ems.models.ems.EMS._EMS__save_consignment')
    @patch('app.shipping.methods.ems.models.ems.get_json')
    def test_consign_raises_order_error_on_submit_failure(self, get_json_mock, save_mock, create_mock):
        """ConsignException raised at line 337 (__submit_consignment) is wrapped as OrderError"""
        create_mock.return_value = 'CONS123'
        save_mock.return_value = None
        get_json_mock.return_value = {'failed': [{'message': 'EMS rejected the consignment'}]}

        ems = EMS()
        sender = Address(address_1_eng='1 Sender St', address_2_eng='', city_eng='Seoul',
                         country_id='kr', zip='12345')
        sender_contact = ShippingContact(name='Sender Name', phone='010-1234-5678')
        recipient = Address(address_1_eng='1 Rcpt St', address_2_eng='', city_eng='Kyiv',
                            country_id='ua', zip='01001')
        rcpt_contact = ShippingContact(name='Recipient Name', phone='+380501234567')

        with self.assertRaises(OrderError):
            ems.consign(sender, sender_contact, recipient, rcpt_contact, [], [Box(42, 30, 19, 1000)])

    @patch('app.shipping.methods.ems.models.ems.EMS.print')
    def test_print_label_non_ems(self, po_mock):
        po_mock.return_value = {}
        self.try_add_entity(Shipping())
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending)
        order.shipping = db.session.get(Shipping, 1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/admin/shipping/ems/label?order_id={order.id}'))
        self.assertEqual(res.status_code, 400)
