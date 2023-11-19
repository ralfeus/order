from tests import BaseTestCase, db
from app.models import Country
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
