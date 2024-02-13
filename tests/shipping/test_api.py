from datetime import datetime
from typing import Any

from app.models import Country
from app.users.models import Role, User
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
import app.products.models as p
import app.shipping.models as s

from tests import BaseTestCase, db

class FakeShipping(s.Shipping):
    __mapper_args__ = {"polymorphic_identity": "fake_shipping"}  # type: ignore

    name = "FakeShipping"
    type = "Fake"

    def consign(self, order: Order, config: dict[str, Any] = {}) -> s.ConsignResult:
        return s.ConsignResult('XXX')
    
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
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending)
        order.shipping = s.Shipping.query.get(1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/api/v1/admin/shipping/consign/{order.id}'))
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(gen_id)
        self.assertEqual(order.tracking_id, 'XXX')
        self.assertEqual(order.tracking_url, 'https://t.17track.net/en#nums=XXX')
