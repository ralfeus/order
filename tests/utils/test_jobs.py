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
        product = db.session.get(p.Product, ('000', 'Atomy'))
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
        product = db.session.get(p.Product, ('000', 'Atomy'))
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
            id=product_id, vendor='Atomy', vendor_id=product_id, name='Test product',
            price=price, points=10, available=True, synchronize=True,
            image=File(file_name='img.png', path='/products/img.png')
        ))

    @staticmethod
    def _get(product_id):
        return db.session.get(p.Product, (product_id, 'Atomy'))

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_no_duplicate_for_zero_padded_id(
            self, get_atomy_products, save_image):
        self._add_local_product('247')
        get_atomy_products.return_value = [
            self._vendor_product('247'), self._vendor_product('000247')]
        jobs.import_products()
        self.assertIsNone(self._get('000247'))
        self.assertEqual(p.Product.get_product_by_id('247').id, '247')
        self.assertTrue(self._get('247').available)

    @patch('app.jobs.save_image', return_value=('', ''))
    @patch('app.jobs.get_atomy_products')
    def test_import_products_matches_padded_vendor_id_to_short_local_id(
            self, get_atomy_products, save_image):
        self._add_local_product('247', price=10)
        get_atomy_products.return_value = [
            self._vendor_product('000247', price=20)]
        jobs.import_products()
        self.assertIsNone(self._get('000247'))
        product = self._get('247')
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
        self.assertTrue(self._get('247').available)
        self.assertFalse(self._get('300').available)

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
            [self._get(i).available for i in ('247', '000247')].count(True), 1)


def _item(product_id, **kwargs):
    return {'id': product_id, 'vendor_id': product_id, 'name': f'Name {product_id}',
            'price': 100, 'points': 10, 'available': True,
            'image_url': f'https://img/{product_id}.jpg', **kwargs}


@patch('app.jobs.save_image', return_value=('/products/x.jpg', 'x.jpg'))
class TestSyncProducts(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        self.try_add_entities([
            p.Product(id='000123', vendor='Atomy', name='Atomy 123', price=1),
            p.Product(id='000123', vendor='AtomyAza', name='AZA 123', price=2),
            p.Product(id='555', vendor='AtomyAza', name='AZA 555', price=5),
        ])

    def _get(self, key):
        db.session.expire_all()
        return p.Product.get_by_key(key)

    def test_atomy_import_keeps_other_vendors(self, _save_image):
        with patch('app.jobs.get_atomy_products', return_value=[{
                'id': '000999', 'atomy_id': '000999', 'name': 'New', 'price': 9,
                'points': 1, 'available': True, 'image_url': ''}]):
            jobs.import_products()
        self.assertFalse(self._get('Atomy:000123').available)
        self.assertTrue(self._get('AtomyAza:000123').available)
        self.assertTrue(self._get('AtomyAza:555').available)
        self.assertEqual(self._get('Atomy:000999').name, 'New')

    def test_sync_vendor(self, _save_image):
        jobs._sync_products('AtomyAza', [
            _item('000123', name='Renamed', price=200),
            _item('695221:4540592')
        ])
        self.assertEqual(self._get('AtomyAza:000123').name, 'Renamed')
        self.assertEqual(self._get('AtomyAza:000123').price, 200)
        self.assertEqual(self._get('AtomyAza:695221:4540592').vendor_id, '695221:4540592')
        self.assertFalse(self._get('AtomyAza:555').available)
        # Other vendor's product with the same ID isn't touched
        atomy = self._get('Atomy:000123')
        self.assertEqual((atomy.name, atomy.price, atomy.available), ('Atomy 123', 1, True))

    def test_unknown_price_keeps_existing(self, _save_image):
        jobs._sync_products('AtomyAza', [
            _item('555', price=None, points=None, available=False),
            _item('777', price=None, points=None)])
        product = self._get('AtomyAza:555')
        self.assertEqual(product.price, 5)
        self.assertFalse(product.available)
        self.assertEqual(self._get('AtomyAza:777').price, 0)
        self.assertEqual(self._get('AtomyAza:777').points, 0)

    def test_empty_feed_changes_nothing(self, _save_image):
        jobs._sync_products('AtomyAza', [])
        self.assertTrue(self._get('AtomyAza:555').available)

    def test_image_failure_doesnt_stop_import(self, save_image):
        save_image.side_effect = [Exception('timeout'), ('/products/b.jpg', 'b.jpg')]
        jobs._sync_products('AtomyAza', [_item('777'), _item('888'), _item('555')])
        self.assertIsNone(self._get('AtomyAza:777').image)
        self.assertEqual(self._get('AtomyAza:888').image.path, '/products/b.jpg')

    def test_missing_image_is_retried(self, save_image):
        jobs._sync_products('AtomyAza', [_item('555')])
        self.assertEqual(self._get('AtomyAza:555').image.path, '/products/x.jpg')

    def test_too_long_id_is_skipped(self, _save_image):
        jobs._sync_products('AtomyAza', [_item('1234567:123456789'), _item('555')])
        self.assertIsNone(self._get('AtomyAza:1234567:123456789'))
        self.assertTrue(self._get('AtomyAza:555').available)

    def test_not_synchronized_product_missing_in_feed_is_kept(self, _save_image):
        product = self._get('AtomyAza:555')
        product.synchronize = False
        db.session.commit()
        jobs._sync_products('AtomyAza', [_item('000123')])
        self.assertTrue(self._get('AtomyAza:555').available)

    def test_not_synchronized_product_in_feed_isnt_updated(self, _save_image):
        product = self._get('AtomyAza:555')
        product.synchronize = False
        db.session.commit()
        jobs._sync_products('AtomyAza', [_item('555', name='Changed', price=999)])
        product = self._get('AtomyAza:555')
        self.assertEqual((product.name, product.price), ('AZA 555', 5))

    def test_leading_zeros_are_ignored_in_matching(self, _save_image):
        '''Leading zeros are ignored for all vendors, so "0555" is the same as "555"'''
        jobs._sync_products('AtomyAza', [_item('0555', name='Zero'), _item('000123')])
        self.assertEqual(self._get('AtomyAza:555').name, 'Zero')
        self.assertTrue(self._get('AtomyAza:555').available)
        self.assertIsNone(self._get('AtomyAza:0555'))

    def test_product_missing_in_partial_feed_is_reenabled_later(self, _save_image):
        '''A product whose page failed to load is disabled until the next import'''
        jobs._sync_products('AtomyAza', [_item('000123')])
        self.assertFalse(self._get('AtomyAza:555').available)
        jobs._sync_products('AtomyAza', [_item('000123'), _item('555')])
        self.assertTrue(self._get('AtomyAza:555').available)

    def test_duplicates_in_feed(self, _save_image):
        jobs._sync_products('AtomyAza', [_item('777'), _item('777', name='Again')])
        self.assertEqual(
            p.Product.query.filter_by(vendor='AtomyAza', id='777').count(), 1)


@patch('app.jobs.save_image', return_value=('', ''))
@patch('app.jobs.get_aza_products')
class TestImportAzaProducts(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        from app.settings.models.setting import Setting
        self.setting = Setting(key='product_import.aza.categories', value='011, 007\n015001')
        self.try_add_entities([
            self.setting,
            p.Product(id='555', vendor='Atomy', name='Atomy 555'),
            p.Product(id='555', vendor='AtomyAza', name='AZA 555'),
            p.Product(id='666', vendor='AtomyAza', name='AZA 666'),
        ])
        self.app.config['AZA_LOGIN'] = '12345678'
        self.app.config['AZA_PASSWORD'] = 'secret'
        self.app.config['AZA_SOCKS5_PROXY'] = ''

    def tearDown(self):
        for key in ['AZA_LOGIN', 'AZA_PASSWORD', 'AZA_SOCKS5_PROXY']:
            self.app.config.pop(key, None)
        super().tearDown()

    def _get(self, key):
        db.session.expire_all()
        return p.Product.get_by_key(key)

    def test_import(self, get_aza_products, _save_image):
        get_aza_products.return_value = [
            {'vendor': 'AtomyAza', 'vendor_id': '555', 'name': 'Renamed', 'price': 10,
             'points': 1, 'available': True, 'image_url': ''},
            {'vendor': 'AtomyAza', 'vendor_id': '695221:4540592', 'name': 'Option',
             'price': 20, 'points': 2, 'available': True, 'image_url': ''},
        ]
        jobs.import_aza_products()
        args, kwargs = get_aza_products.call_args
        self.assertEqual(args[:3], ('12345678', 'secret', ['011', '007', '015001']))
        self.assertEqual(self._get('AtomyAza:555').name, 'Renamed')
        self.assertEqual(self._get('AtomyAza:695221:4540592').vendor_id, '695221:4540592')
        self.assertFalse(self._get('AtomyAza:666').available)
        self.assertEqual(self._get('Atomy:555').name, 'Atomy 555')
        self.assertTrue(self._get('Atomy:555').available)

    def test_no_categories(self, get_aza_products, _save_image):
        self.setting.value = ' , '
        db.session.commit()
        jobs.import_aza_products()
        get_aza_products.assert_not_called()
        self.assertTrue(self._get('AtomyAza:666').available)

    def test_no_setting(self, get_aza_products, _save_image):
        db.session.delete(self.setting)
        db.session.commit()
        jobs.import_aza_products()
        get_aza_products.assert_not_called()

    def test_no_credentials(self, get_aza_products, _save_image):
        del self.app.config['AZA_PASSWORD']
        with self.assertLogs('import_aza_products', level='ERROR'):
            jobs.import_aza_products()
        get_aza_products.assert_not_called()

    def test_login_error_doesnt_sync(self, get_aza_products, _save_image):
        from common.utils.aza import AzaLoginError
        get_aza_products.side_effect = AzaLoginError('Session expired')
        with self.assertLogs('import_aza_products', level='ERROR'):
            jobs.import_aza_products()
        self.assertTrue(self._get('AtomyAza:555').available)
        self.assertTrue(self._get('AtomyAza:666').available)

    def test_empty_result_doesnt_disable(self, get_aza_products, _save_image):
        get_aza_products.return_value = []
        jobs.import_aza_products()
        self.assertTrue(self._get('AtomyAza:666').available)


class TestPeriodicTasks(BaseTestCase):
    def test_schedule(self):
        from unittest.mock import MagicMock
        sender = MagicMock()
        jobs.setup_periodic_tasks(sender)
        tasks = {call.args[1]: call.args[0] for call in sender.add_periodic_task.call_args_list}
        self.assertEqual(tasks[jobs.import_products], 28800)
        self.assertEqual(tasks[jobs.import_aza_products], 86400)
