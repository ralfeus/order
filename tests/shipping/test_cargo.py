from tests import BaseTestCase, db
from app.models import Country
from app.users.models.role import Role
from app.users.models.user import User
from app.shipping.methods.cargo.models import Cargo
from app.shipping.models.shipping_rate import ShippingRate

class TestShippingCargo(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_cargo_api',
            email='user_test_cargo_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True)
        self.admin = User(username='root_test_cargo_api',
            email='root_test_cargo_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])

        # Create test countries
        countries = [
            Country(id='us', name='United States', sort_order=1),
            Country(id='ca', name='Canada', sort_order=2),
            Country(id='mx', name='Mexico', sort_order=3),
            Country(id='gb', name='United Kingdom', sort_order=4),
        ]

        # Create cargo shipping method
        cargo = Cargo(id=1, name='Cargo Shipping', enabled=True)

        # Create some initial rates
        rates = [
            ShippingRate(shipping_method_id=1, destination='us', weight=0, rate=0),
            ShippingRate(shipping_method_id=1, destination='ca', weight=0, rate=0),
        ]

        self.try_add_entities([
            self.user, self.admin, admin_role
        ] + countries + [cargo] + rates)

    def test_admin_get_countries_valid_shipping(self):
        """Test GET /api/v1/admin/shipping/cargo/1/countries with valid shipping ID"""
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/shipping/cargo/1/countries')
        )
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertIn('data', data)
        self.assertGreater(len(data['data']), 0)

        # Check that countries are returned with selection status
        countries = data['data']
        us_country = next((c for c in countries if c['id'] == 'us'), None)
        ca_country = next((c for c in countries if c['id'] == 'ca'), None)
        mx_country = next((c for c in countries if c['id'] == 'mx'), None)

        self.assertIsNotNone(us_country)
        self.assertIsNotNone(ca_country)
        self.assertIsNotNone(mx_country)

        # Check selection status
        self.assertTrue(us_country['selected'])
        self.assertTrue(ca_country['selected'])
        self.assertFalse(mx_country['selected'])

    def test_admin_get_countries_invalid_shipping(self):
        """Test GET /api/v1/admin/shipping/cargo/999/countries with invalid shipping ID"""
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/shipping/cargo/999/countries')
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn('No shipping found', res.get_json()['status'])

    def test_admin_save_rate_valid(self):
        """Test POST /api/v1/admin/shipping/cargo/1/rate with valid data"""
        initial_count = ShippingRate.query.count()

        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/1/rate', json={
                'destination': 'mx'
            })
        )
        self.assertEqual(res.status_code, 200)

        # Check that rate was created
        self.assertEqual(ShippingRate.query.count(), initial_count + 1)

        # Verify the rate details
        rate = ShippingRate.query.filter_by(shipping_method_id=1, destination='mx').first()
        self.assertIsNotNone(rate)
        self.assertEqual(rate.weight, 0)
        self.assertEqual(rate.rate, 0)

    def test_admin_save_rate_duplicate_destination(self):
        """Test POST /api/v1/admin/shipping/cargo/1/rate with duplicate destination"""
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/1/rate', json={
                'destination': 'us'  # Already exists
            })
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('Rate for us already exists', res.get_json()['error'])

    def test_admin_save_rate_missing_destination(self):
        """Test POST /api/v1/admin/shipping/cargo/1/rate with missing destination"""
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/1/rate', json={})
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('Destination required', res.get_json()['error'])

    def test_admin_save_rate_invalid_shipping(self):
        """Test POST /api/v1/admin/shipping/cargo/999/rate with invalid shipping ID"""
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/999/rate', json={
                'destination': 'mx'
            })
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn('No shipping 999 found', res.get_json()['error'])

    def test_admin_delete_rate_valid(self):
        """Test DELETE /api/v1/admin/shipping/cargo/1/rate/us with valid data"""
        initial_count = ShippingRate.query.count()

        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/shipping/cargo/1/rate/us')
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['status'], 'success')

        # Check that rate was deleted
        self.assertEqual(ShippingRate.query.count(), initial_count - 1)

        # Verify the rate no longer exists
        rate = ShippingRate.query.filter_by(shipping_method_id=1, destination='us').first()
        self.assertIsNone(rate)

    def test_admin_delete_rate_nonexistent(self):
        """Test DELETE /api/v1/admin/shipping/cargo/1/rate/gb with non-existent rate"""
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/shipping/cargo/1/rate/gb')
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn('No rate for destination gb found', res.get_json()['error'])

    def test_admin_delete_rate_invalid_shipping(self):
        """Test DELETE /api/v1/admin/shipping/cargo/999/rate/us with invalid shipping ID"""
        res = self.try_admin_operation(
            lambda: self.client.delete('/api/v1/admin/shipping/cargo/999/rate/us')
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn('No shipping 999 found', res.get_json()['error'])

    def test_admin_save_countries_valid(self):
        """Test POST /api/v1/admin/shipping/cargo/1/countries with valid bulk update"""
        # Start with us, ca selected
        # Want to select us, gb and deselect ca
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/1/countries', json={
                'selected_countries': ['us', 'gb']
            })
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['status'], 'success')

        # Check final state
        cargo = Cargo.query.get(1)
        selected_destinations = {rate.destination for rate in cargo.rates}

        self.assertEqual(selected_destinations, {'us', 'gb'})

        # Verify rate details
        gb_rate = ShippingRate.query.filter_by(shipping_method_id=1, destination='gb').first()
        self.assertIsNotNone(gb_rate)
        self.assertEqual(gb_rate.weight, 0)
        self.assertEqual(gb_rate.rate, 0)

    def test_admin_save_countries_empty_payload(self):
        """Test POST /api/v1/admin/shipping/cargo/1/countries with empty payload"""
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/1/countries', json={})
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('Selected countries required', res.get_json()['error'])

    def test_admin_save_countries_invalid_shipping(self):
        """Test POST /api/v1/admin/shipping/cargo/1/countries with invalid shipping ID"""
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/shipping/cargo/999/countries', json={
                'selected_countries': ['us']
            })
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn('No shipping 999 found', res.get_json()['error'])
