from tests import BaseTestCase, db
class TestShippingAPI(BaseTestCase):
    def test_get_boxes(self):
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/shipping/box'))
        self.assertEqual(res.status_code, 200)