from tests import BaseTestCase, db
from app.models import Country
from app.users.models import Role, User
from app.shipping.methods.dhl.models.dhl import DHL, DHLCountry, DHLRate, DHLZone

class TestShippingDHL(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_dhl_api',
            email='root_test_dhl_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True)
        self.admin = User(username='root_test_dhl_api',
            email='root_test_dhl_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        # db.session.execute("INSERT INTO dhl_zones VALUES(1)")
        # db.session.execute("INSERT INTO dhl_zones VALUES(2)")
        # db.session.execute("INSERT INTO dhl_zones VALUES(3)")
        # db.session.execute("INSERT INTO dhl_zones VALUES(4)")
        # db.session.execute("INSERT INTO dhl_zones VALUES(5)")
        # db.session.execute("INSERT INTO dhl_zones VALUES(6)")
        db.session.execute("INSERT INTO dhl_zones VALUES(7)")
        db.session.execute("INSERT INTO dhl_zones VALUES(8)")
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Country(id='ua', name='Ukraine', sort_order=0),
            Country(id='cz', name='Czech Republic'),
            Country(id='de', name='Germany'),
            DHLCountry(country_id='de', zone=7),
            DHLCountry(country_id='ua', zone=8),
            DHLCountry(country_id='cz', zone=7),
            DHLRate(zone=7, weight=0.5, rate=10),
            DHLRate(zone=7, weight=10, rate=100),
            DHLRate(zone=7, weight=99999, rate=13975),
            DHLRate(zone=8, weight=0.5, rate=44339),
            DHLRate(zone=8, weight=10, rate=180919),
            DHLRate(zone=8, weight=99999, rate=13975)
        ])


    def test_get_rate(self):
        dhl = DHL()
        rate = dhl.get_shipping_cost('ua', 100)
        self.assertEqual(rate, 44339)
        rate = dhl.get_shipping_cost('ua', 100000)
        self.assertEqual(rate, 1397500)

    def test_get_rates(self):
        res = self.try_admin_operation(lambda:
            self.client.get('/api/v1/admin/shipping/dhl/rate')
        )
        self.assertEqual(res.json, {'data': [
            {'weight': 0.5, 'zone_7': 10, 'zone_8': 44339},
            {'weight': 10.0, 'zone_7': 100, 'zone_8': 180919},
            {'weight': 99999.0, 'zone_7': 13975, 'zone_8': 13975}
        ]})
