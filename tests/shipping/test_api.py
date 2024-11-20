from datetime import datetime
from typing import Any

from app.models import Country
from app.models.address import Address
from app.shipping.models.box import Box
from app.shipping.models.consign_result import ConsignResult
from app.shipping.models.shipping import Shipping
from app.shipping.models.shipping_contact import ShippingContact
from app.shipping.models.shipping_item import ShippingItem
from app.users.models import Role, User
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.payments.models.payment_method import PaymentMethod
from app.purchase.models.company import Company
import app.products.models as p

from tests import BaseTestCase, db

class FakeShipping(Shipping):
    __mapper_args__ = {"polymorphic_identity": "fake_shipping"}  # type: ignore

    name = "FakeShipping"
    type = "Fake"

    def consign(self, sender: Address, sender_contact: ShippingContact, 
                recipient: Address, rcpt_contact: ShippingContact,
                items: list[ShippingItem], boxes: list[Box], config: dict[str, Any]
                ) -> ConsignResult:
        return ConsignResult('XXX')
    
    def get_shipping_items(self, items: list[str]) -> list[ShippingItem]:
        return []

    
class TestShippingAPI(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_shipping_api', email='root_test_shipping_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True, roles=[Role(name='allow_create_po')])
        self.admin = User(username='root_test_shipping_api', email='root_test_shipping_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Country(id='c1', name='country1'),
            p.Product(id='0000', name='Test product', price=10, weight=10),
            FakeShipping(id=1, name='Shipping1'),
        ])

    def test_consign(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        country = Country(id='kr', name='Korea')
        address = Address(id=1, address_1_eng='a1', address_2_eng='a2', 
                        city_eng='c1', zip='00', country_id='kr')
        company = Company(name='Company1', address=address)
        payment_method = PaymentMethod(id=1, payee=company)
        self.try_add_entities([country, address, company, payment_method])
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending, 
                      payment_method_id=1, address='aa1', city_eng='cc1', 
                      zip='11', country_id='c1', shipping_box_weight=250)
        order.shipping = Shipping.query.get(1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/api/v1/admin/shipping/consign/{order.id}'))
        self.assertEqual(res.status_code, 200)
        print(res.get_json())
        order = Order.query.get(gen_id)
        self.assertEqual(order.tracking_id, 'XXX')
        self.assertEqual(order.tracking_url, 'https://t.17track.net/en#nums=XXX')

    def test_consign_with_custom_items(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        country = Country(id='kr', name='Korea')
        address = Address(id=1, address_1_eng='a1', address_2_eng='a2', 
                        city_eng='c1', zip='00', country_id='kr')
        company = Company(name='Company1', address=address)
        payment_method = PaymentMethod(id=1, payee=company)
        self.try_add_entities([country, address, company, payment_method])
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending, 
                      payment_method_id=1, address='aa1', city_eng='cc1', 
                      zip='11', country_id='c1', shipping_box_weight=250, 
                      params={'shipping.items': 'Item 1/5/10\nItem 2/5/20'})
        order.shipping = Shipping.query.get(1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/api/v1/admin/shipping/consign/{order.id}'))
        self.assertEqual(res.status_code, 200)
        print(res.get_json())
        order = Order.query.get(gen_id)
        self.assertEqual(order.tracking_id, 'XXX')
        self.assertEqual(order.tracking_url, 'https://t.17track.net/en#nums=XXX')

