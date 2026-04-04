from unittest.mock import patch

from bs4 import BeautifulSoup
from tests import BaseTestCase

from app import db
import app.jobs as jobs
import app.products.models as p
    
class TestJobs(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()

    @patch('app.jobs.save_image')
    @patch('common.utils.atomy.atomy_login2')
    @patch('common.utils.get_json')
    @patch('common.utils.get_document')
    def test_import_products(self, get_document, get_json, atomy_login2, save_image):
        atomy_login2.return_value = None
        get_document.return_value = BeautifulSoup('''
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
            ''', 'html.parser')
        get_json.return_value = [
            {
                "itemNo": "00000", 
                "sortSeq": 0, 
                "salePossQty": 0, 
                "materialCode": "001846", 
                "goodsStatCd": "20", 
                "goodsStatNm": "goods.word.outofstock", 
                "goodsTypeCd": "101", 
                "soldOutWarehouseList": [
                    {
                        "warehouseNo": "01", 
                        "itemNo": "00000", 
                        "regDaysDiff": 0, 
                        "warehouseNm": "KR", 
                        "salePossQty": 0, 
                        "totalSalePossQty": 0
                    }
                ], 
                "pvPrice": 0.0, 
                "nomeSalePrice": 0.0, 
                "custSalePrice": 0.0, 
                "beneCustSalePrice": 0.0, 
                "custPvupPrice": 0.0, 
                "reservSaleMgmtNo": "", 
                "reservTotalMemberQty": 0, 
                "reservTotalOrdQty": 0
            }
        ]
        save_image.return_value = '', ''
        self.try_add_entity(p.Product(
            id='000', synchronize=True
        ))
        jobs.import_products()
        product = db.session.get(p.Product, '000')
        self.assertEqual(product.vendor_id, '000')