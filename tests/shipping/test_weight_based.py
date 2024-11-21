from tests import BaseTestCase, db
from app.models import Country
from app.users.models.role import Role
from app.users.models.user import User
from app.shipping.methods.weight_based.models import WeightBased, WeightBasedRate

class TestShippingWeightBased(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_weight_based_api',
            email='root_test_weight_based_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True)
        self.admin = User(username='root_test_weight_based_api',
            email='root_test_weight_based_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Country(id='ua', name='Ukraine'),
            Country(id='c1', name='C1'),
            WeightBased(id=1, name='S', enabled=True),
            WeightBasedRate(shipping_id=1, destination='ua', minimum_weight=1000,
                maximum_weight=30000, weight_step=100, cost_per_kg=1000)
        ])

    def test_get_rate(self):
        from exceptions import NoShippingRateError
        shipping = WeightBased.query.get(1)
        rate = shipping.get_shipping_cost('ua', 100)
        self.assertEqual(rate, 1000)
        rate = shipping.get_shipping_cost('ua', 10000)
        self.assertEqual(rate, 10000)
        with self.assertRaises(NoShippingRateError):
            shipping.get_shipping_cost('ua', 35000)

    def test_get_rates_api(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/shipping/weight_based/1/rate')
        )
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/api/v1/shipping/rate/ua/1/1450')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['shipping_cost'], 1500)

    def test_create_rate_api(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/weight_based/1/rate', json={
                'destination': 'c1',
                'minimum_weight': 1,
                'maximum_weight': 10,
                'weight_step': 1,
                'cost_per_kg': 1
            })
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(WeightBasedRate.query.count(), 2)

    def test_cache_clear(self):
        res = self.try_user_operation(lambda: self.client.get('/api/v1/shipping/rate/ua/900'))
        assert res.json['1'] == 1000
        self.try_admin_operation(lambda: self.client.post('/api/v1/admin/shipping/weight_based/1/rate/-ua', json={
                'minimum_weight': 1000,
                'maximum_weight': 10000,
                'weight_step': 1,
                'cost_per_kg': 1
            }))
        res = self.client.get('/api/v1/shipping/rate/ua/900')
        assert res.json['1'] == 1