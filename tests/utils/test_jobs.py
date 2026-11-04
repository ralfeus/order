from unittest.mock import patch

from bs4 import BeautifulSoup
from tests import BaseTestCase

from app import db
import app.jobs as jobs
import app.products.models as p
from app.models.file import File
    
class TestJobs(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()

    @patch('app.jobs.save_image')
    @patch('product_importer.import_products.set_language')
    @patch('product_importer.import_products.atomy_login2')
    @patch('product_importer.import_products.get_json')
    @patch('product_importer.import_products.get_document')
    def test_import_products(self, get_document, get_json, atomy_login2, set_language, save_image):
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
    @patch('app.jobs.save_image')
    @patch('app.jobs.get_atomy_products')
    def test_import_products_keeps_uploaded_image(self, get_atomy_products, save_image):
        get_atomy_products.return_value = [{
            'id': '000', 'atomy_id': '000', 'name': 'Test product',
            'price': 10, 'points': 10, 'available': True,
            'image_url': 'https://image.atomy.com/vendor.jpg'
        }]
        self.try_add_entity(p.Product(
            id='000', vendor_id='000', name='Test product', price=10, points=10,
            available=True, synchronize=True,
            image=File(file_name='mine.png', path='/products/000-uploaded.png')
        ))
        jobs.import_products()
        save_image.assert_not_called()
        product = db.session.get(p.Product, '000')
        self.assertEqual(product.image.path, '/products/000-uploaded.png')

    @staticmethod
    def _vendor_product(product_id, price=10, available=True):
        return {
            'id': product_id, 'atomy_id': product_id, 'name': 'Test product',
            'price': price, 'points': 10, 'available': available,
            'image_url': ''
        }

    def _add_local_product(self, product_id, price=10):
        self.try_add_entity(p.Product(
            id=product_id, vendor_id=product_id, name='Test product',
            price=price, points=10, available=True, synchronize=True,
            image=File(file_name='img.png', path='/products/img.png')
        ))

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_no_duplicate_for_zero_padded_id(
            self, get_atomy_products, save_image):
        self._add_local_product('247')
        get_atomy_products.return_value = [
            self._vendor_product('247'), self._vendor_product('000247')]
        jobs.import_products()
        self.assertIsNone(db.session.get(p.Product, '000247'))
        self.assertEqual(p.Product.get_product_by_id('247').id, '247')
        self.assertTrue(db.session.get(p.Product, '247').available)

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_matches_padded_vendor_id_to_short_local_id(
            self, get_atomy_products, save_image):
        self._add_local_product('247', price=10)
        get_atomy_products.return_value = [
            self._vendor_product('000247', price=20)]
        jobs.import_products()
        self.assertIsNone(db.session.get(p.Product, '000247'))
        product = db.session.get(p.Product, '247')
        self.assertEqual(product.price, 20)
        self.assertTrue(product.available)

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_creates_single_product_for_duplicate_vendor_ids(
            self, get_atomy_products, save_image):
        get_atomy_products.return_value = [
            self._vendor_product('247'), self._vendor_product('000247')]
        jobs.import_products()
        self.assertEqual(p.Product.query.count(), 1)
        self.assertIsNotNone(p.Product.get_product_by_id('247'))

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_disables_unmatched_local_product(
            self, get_atomy_products, save_image):
        self._add_local_product('247')
        self._add_local_product('300')
        get_atomy_products.return_value = [self._vendor_product('000247')]
        jobs.import_products()
        self.assertTrue(db.session.get(p.Product, '247').available)
        self.assertFalse(db.session.get(p.Product, '300').available)

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_disables_existing_local_duplicate(
            self, get_atomy_products, save_image):
        self._add_local_product('247')
        self._add_local_product('000247')
        get_atomy_products.return_value = [self._vendor_product('247')]
        jobs.import_products()
        self.assertEqual(p.Product.query.count(), 2)
        self.assertEqual(
            [db.session.get(p.Product, i).available for i in ('247', '000247')]
            .count(True), 1)
