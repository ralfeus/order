from datetime import datetime
from unittest.mock import patch
from tests import BaseTestCase, db
from app.models import Country
import app.orders.models as o
import app.shipping.models as s
from app.users.models import Role, User
from app.shipping.methods.ems.models import EMS

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

    @patch('app.shipping.methods.ems.models.ems:EMS.print')
    def test_print_label(self, po_mock):
        po_mock.return_value = {}
        self.try_add_entity(EMS())
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = o.Order(id=gen_id, user=self.user, status=o.OrderStatus.pending)
        order.shipping = s.Shipping.query.get(1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/admin/shipping/ems/label?order_id={order.id}'))
        self.assertEqual(res.status_code, 200)
        order = o.Order.query.get(gen_id)
        self.assertEqual(order.status, o.OrderStatus.shipped)

    @patch('app.shipping.methods.ems.models.ems:EMS.print')
    def test_print_label_non_ems(self, po_mock):
        po_mock.return_value = {}
        self.try_add_entity(s.Shipping())
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = o.Order(id=gen_id, user=self.user, status=o.OrderStatus.pending)
        order.shipping = s.Shipping.query.get(1)
        self.try_add_entities([order])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/admin/shipping/ems/label?order_id={order.id}'))
        self.assertEqual(res.status_code, 400)
