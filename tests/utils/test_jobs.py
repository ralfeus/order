from unittest.mock import patch
from tests import BaseTestCase

from lxml import etree
from app import db
import app.jobs as jobs
import app.products.models as p


class TestJobs(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()

    @patch('app.jobs.save_image')
    @patch('utils.atomy.atomy_login2')
    @patch('app.tools.get_json')
    @patch('app.tools.get_html')
    def test_import_products(self, get_html, get_json, atomy_login2, save_image):
        atomy_login2.return_value = None
        get_html.return_value = etree.fromstring('''
            <div class="gdsList n5">
                <input type="hidden" name="pageIdx" value="1">
                <input type="hidden" name="rowsPerPage" value="40">
                <input type="hidden" name="totalCount" value="1">
                <ul class="gdsList-wrap">
                    <li>
                            <div class="gdImg">
                                <a href="https://kr.atomy.com/product/000">
                                    <span class="img"><img src="//image.atomy.com/KR/goods/000000/c60c6d4f-f293-4273-b77d-9c7e20bf47a5.jpg?w=480&h=480" onerror="this.src='//resources.atomy.com/20250612110037/common/images/no_img_square.jpg'" alt="Atomy Toothbrush *1set(8ea)"></span>
                                </a>
                            </div>
                            <div class="gdInfo">
                                <button type="button" class="bt_cart" aria-haspopup="dialog" onclick="javascript:overpass.disp.optionLayerCreate({goodsNo : '000510'});" aria-label="Open Add to Cart Layer"></button>
                                <a href="https://kr.atomy.com/product/000000">
                                    <span class="title">Test product</span>
                                    <span class="gdsPrice"><span class="prc"><span class="prc_ori"><b>10</b><em>KRW</em></span></span><span class="pv"><span class="pv_ori"><b>10</b><em>PV</em></span></span></span>
                                    <span class="sales">558 Reviews guaranteed</span>
                                </a>
                            </div>
                    </li>
                </ul>
            </div>
            ''', parser=etree.HTMLParser())
        get_json.return_value = {'00000': {
                    "materialCode": '000',
                    "id": "000",
                    "productName": "Test product",
                    'name': "Test english name",
                    "memRetailPrice": 10,
                    "pvPrice": 10,
                    "flags": ['test_flag'],
                    "images": [{"file": "image file"}],
                    "optionType": {"value": 'none'}
                }}
        save_image.return_value = '', ''
        self.try_add_entity(p.Product(
            id='000', synchronize=True
        ))
        jobs.import_products()
        product = p.Product.query.get('000')
        self.assertEqual(product.vendor_id, '000')