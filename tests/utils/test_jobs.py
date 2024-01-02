from unittest.mock import patch
from tests import BaseTestCase

from app import db
import app.jobs as jobs
import app.products.models as p


class TestJobs(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()

    @patch('app.jobs.save_image')
    @patch('app.utils.atomy.atomy_login2')
    @patch('app.tools.get_json')
    def test_import_products(self, get_json, atomy_login2, save_image):
        atomy_login2.return_value = None
        get_json.return_value = {
            'result': '200',
            'pageCount': 1,
            'items': [{
                    "materialCode": '000',
                    "id": "000",
                    "productName": "Test product",
                    'name': "Test english name",
                    "memRetailPrice": 10,
                    "pvPrice": 10,
                    "flags": ['test_flag'],
                    "images": [{"file": "image file"}],
                    "optionType": {"value": 'none'}
                }]
        }
        save_image.return_value = '', ''
        self.try_add_entity(p.Product(
            id='000', synchronize=True
        ))
        jobs.import_products()
        product = p.Product.query.get('000')
        self.assertEqual(product.vendor_id, '000')