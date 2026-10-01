'''Tests for the AtomyAza (atomyaza.co.kr) product importer.
All HTTP traffic is faked with fixtures from tests/products/fixtures/aza'''
import json
import os
from unittest import TestCase
from unittest.mock import MagicMock

from bs4 import BeautifulSoup

from common.utils.aza import AzaLoginError, aza_login, normalize_member_id
from product_importer.aza import (
    VENDOR, GroupProductError, get_aza_products, get_categories, resolve_categories,
    _get_products_list, _parse_cards, _parse_product)

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'aza')

def _fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()

def _response(text: str='', status: int=200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    response.json.side_effect = lambda: json.loads(text)
    response.raise_for_status.side_effect = None if status < 400 \
        else Exception(f'HTTP {status}')
    return response


class FakeSession:
    '''Serves fixtures by URL path, list pages by the "page" parameter
    and product pages by the "gs_id" parameter'''
    def __init__(self, list_pages: dict[int, str], views: dict[str, str]):
        self.list_pages = list_pages
        self.views = views
        self.list_calls = []

    def get(self, url, params=None, timeout=None):
        params = params or {}
        if url.endswith('/m/'):
            return _response(_fixture('home.html'))
        if url.endswith('/m/shop/ajax.list.php'):
            self.list_calls.append(dict(params))
            name = self.list_pages.get(params['page'])
            return _response(_fixture(name) if name
                             else json.dumps({'str': '', 'page': params['page'], 'err': 1}))
        if url.endswith('/m/shop/view.php'):
            name = self.views.get(str(params['gs_id']))
            if name is None:
                return _response('', 500)
            return _response(_fixture(name))
        raise AssertionError(f'Unexpected URL {url}')

    OPTION_LEVELS = {'브라운': 'option_level_brown.html', '블랙': 'option_level_black.html'}

    def post(self, url, data=None, headers=None, timeout=None):
        '''Serves lower option levels by the selected upper level value'''
        if url.endswith('/m/shop/view_option.new.php'):
            self.option_calls = getattr(self, 'option_calls', []) + [dict(data)]
            return _response(_fixture(self.OPTION_LEVELS[data['opt_id']]))
        raise AssertionError(f'Unexpected URL {url}')


class TestAzaLogin(TestCase):
    def test_normalize_member_id(self):
        self.assertEqual(normalize_member_id('12345678'), '12345678')
        self.assertEqual(normalize_member_id('1234567'), 'S1234567')
        self.assertEqual(normalize_member_id('12345'), 'S0012345')
        self.assertEqual(normalize_member_id('S1234567'), 'S1234567')

    def test_login_success(self):
        session = MagicMock()
        session.post.return_value = _response(json.dumps({'code': '1', 'url': '/m'}))
        result = aza_login('12345678', 'secret', session=session)
        self.assertIs(result, session)
        data = session.post.call_args.kwargs['data']
        self.assertEqual(data['mb_id'], '12345678')
        self.assertEqual(data['mb_password'], 'secret')

    def test_login_wrong_credentials(self):
        session = MagicMock()
        session.post.return_value = _response(json.dumps({'code': '0', 'error': '비밀번호 오류'}))
        with self.assertRaises(AzaLoginError):
            aza_login('12345678', 'wrong', session=session)

    def test_login_non_json_response(self):
        session = MagicMock()
        session.post.return_value = _response('<html>error</html>')
        with self.assertRaises(AzaLoginError):
            aza_login('12345678', 'secret', session=session)


class TestAzaCategories(TestCase):
    def test_get_categories(self):
        categories = get_categories(FakeSession({}, {}))
        ids = [c['ca_id'] for c in categories]
        self.assertIn('015', ids)
        self.assertIn('011', ids)
        self.assertIn('011002', ids)
        fruit = next(c for c in categories if c['ca_id'] == '011002')
        self.assertEqual(fruit['name'], '과일')
        self.assertEqual(fruit['parent'], '011')
        top = next(c for c in categories if c['ca_id'] == '011')
        self.assertEqual(top['name'], '신선식품')
        self.assertIsNone(top['parent'])

    def test_resolve_categories(self):
        tree = get_categories(FakeSession({}, {}))
        logger = MagicMock()
        result = resolve_categories(['011', ' 015001 ', '999', '', '011002'], tree, logger)
        # 011002 is covered by 011 (prefix match on the site), 999 is unknown
        self.assertEqual(result, ['011', '015001'])
        logger.warning.assert_called_once()

    def test_resolve_categories_empty(self):
        self.assertEqual(resolve_categories([], [], MagicMock()), [])


class TestAzaListParsing(TestCase):
    def test_parse_cards(self):
        html = json.loads(_fixture('list_page1.json'))['str']
        cards = _parse_cards(BeautifulSoup(html, 'html.parser'))
        self.assertEqual(len(cards), 3)
        apple = cards[0]
        self.assertEqual(apple['gs_id'], '695221')
        self.assertEqual(apple['price'], 27900)
        self.assertEqual(apple['points'], 850)
        self.assertTrue(apple['available'])
        self.assertTrue(apple['image_url'].startswith('https://'))
        soldout = cards[2]
        self.assertFalse(soldout['available'])
        self.assertIsNone(soldout['price'])
        self.assertIsNone(soldout['points'])

    def test_parse_cards_big_numbers_and_protocol_relative_image(self):
        html = json.loads(_fixture('list_page2_last.json'))['str']
        card = _parse_cards(BeautifulSoup(html, 'html.parser'))[1]
        self.assertEqual(card['price'], 1000000)
        self.assertEqual(card['points'], 30000)
        self.assertEqual(card['image_url'],
            'https://www.atomyaza.co.kr/data/goods/700001/thumb-700001_450x450.jpg')

    def test_parse_cards_anonymous_session(self):
        html = json.loads(_fixture('list_anonymous.json'))['str']
        with self.assertRaises(AzaLoginError):
            _parse_cards(BeautifulSoup(html, 'html.parser'))

    def test_products_list_pagination_stops_on_err_and_keeps_last_page(self):
        session = FakeSession({1: 'list_page1.json', 2: 'list_page2_last.json'}, {})
        cards = _get_products_list(session, '011')
        self.assertEqual(len(session.list_calls), 2)
        self.assertEqual(session.list_calls[0]['ca_id'], '011')
        # 3 on the first page + 2 on the last one (duplicates are removed later)
        self.assertEqual(len(cards), 5)

    def test_products_list_stops_on_empty_page(self):
        session = FakeSession({1: 'list_page1.json'}, {})
        cards = _get_products_list(session, '011')
        self.assertEqual(len(session.list_calls), 2)
        self.assertEqual(len(cards), 3)


class TestAzaProductParsing(TestCase):
    CARD = {'gs_id': '695221', 'name': 'truncated…', 'price': 27900, 'points': 850,
            'available': True, 'image_url': 'https://img/1.jpg'}

    def test_product_with_options(self):
        doc = BeautifulSoup(_fixture('view_options.html'), 'html.parser')
        products = _parse_product(self.CARD, doc)
        self.assertEqual(len(products), 4)
        full_name = '[팜스온테이블] GAP인증 믿고 먹는 청송사과 달콤 새콤 이지플 사과 2kg~5kg(꼬마/소과/중과/대과)'
        first, second, comma, disabled = products
        self.assertEqual(first['vendor'], VENDOR)
        self.assertEqual(first['vendor_id'], '695221:4541550')
        self.assertEqual(first['name'], f'{full_name} - 이지플 사과 2kg 소과(9-11과 내외)')
        self.assertEqual(first['price'], 27900)
        self.assertEqual(first['points'], 850)
        self.assertTrue(first['available'])
        self.assertEqual(first['image_url'], 'https://img/1.jpg')
        self.assertEqual(second['price'], 34900)
        self.assertEqual(second['points'], 1060)
        # Option name containing a comma; zero stock
        self.assertEqual(comma['vendor_id'], '695221:4541553')
        self.assertTrue(comma['name'].endswith('사과 5kg, 선물용'))
        self.assertEqual(comma['price'], 43900)
        self.assertFalse(comma['available'])
        # Option marked as impossible to buy
        self.assertFalse(disabled['available'])

    def test_product_with_single_option(self):
        card = {**self.CARD, 'gs_id': '694068', 'price': 8300, 'points': 180}
        doc = BeautifulSoup(_fixture('view_single_option.html'), 'html.parser')
        products = _parse_product(card, doc)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]['vendor_id'], '694068')
        self.assertEqual(products[0]['name'],
            '[올심찬] 태국산 프리미엄 냉동 남독마이 망고 500g (18Brix 고당도) 2팩')
        self.assertEqual(products[0]['price'], 8300)
        self.assertEqual(products[0]['points'], 180)
        self.assertTrue(products[0]['available'])

    def test_product_without_options_uses_card(self):
        card = {**self.CARD, 'gs_id': '689859', 'price': None, 'points': None,
                'available': False}
        doc = BeautifulSoup(_fixture('view_no_options.html'), 'html.parser')
        products = _parse_product(card, doc)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]['vendor_id'], '689859')
        self.assertEqual(products[0]['name'],
            '[추석][오늘신선] 경북 상주 둥시 곶감 반건시/건시 선물세트 모음')
        self.assertIsNone(products[0]['price'])
        self.assertFalse(products[0]['available'])

    def test_product_page_of_anonymous_session(self):
        doc = BeautifulSoup(_fixture('view_anonymous.html'), 'html.parser')
        with self.assertRaises(AzaLoginError):
            _parse_product(self.CARD, doc)

    def test_group_product_is_rejected(self):
        doc = BeautifulSoup(
            '<ul><li class="opt_list_li" data-grp_item="1" data-gs_id="1" '
            'data-value="x"></li></ul>', 'html.parser')
        with self.assertRaises(GroupProductError):
            _parse_product(self.CARD, doc)

    def test_long_name_is_truncated(self):
        doc = BeautifulSoup(_fixture('view_options.html').replace(
            '[팜스온테이블]', 'X' * 300), 'html.parser')
        for product in _parse_product(self.CARD, doc):
            self.assertLessEqual(len(product['name']), 256)


class TestGetAzaProducts(TestCase):
    def setUp(self):
        self.session = FakeSession(
            {1: 'list_page1.json', 2: 'list_page2_last.json'},
            {'695221': 'view_options.html', '694068': 'view_single_option.html',
             '689859': 'view_no_options.html'})  # 700001 view fails with HTTP 500
        self.login = MagicMock(return_value=self.session)

    def test_get_aza_products(self):
        logger = MagicMock()
        products = get_aza_products('12345678', 'secret', ['011', '015'],
                                    logger=logger, login=self.login)
        self.login.assert_called_once_with('12345678', 'secret', '')
        ids = sorted(p['vendor_id'] for p in products)
        # Duplicates across pages and categories are removed;
        # 700001 is skipped because its page couldn't be loaded
        self.assertEqual(ids, ['689859', '694068',
            '695221:4541550', '695221:4541551', '695221:4541553', '695221:4541554'])
        self.assertTrue(all(p['vendor'] == VENDOR for p in products))
        logger.warning.assert_called()

    def test_product_with_multilevel_options(self):
        '''Bug: "not enough values to unpack (expected 6, got 1)" for products
        with several option levels (e.g. color and size), e.g. 694437'''
        self.session.views['695221'] = 'view_multilevel.html'
        logger = MagicMock()
        products = get_aza_products('u', 'p', ['011'], logger=logger, login=self.login)
        cardigan = sorted((p for p in products if p['vendor_id'].startswith('695221')),
                          key=lambda p: p['vendor_id'])
        self.assertEqual([p['vendor_id'] for p in cardigan],
            ['695221:4540592', '695221:4540593', '695221:4540594'])
        self.assertEqual(cardigan[0]['name'], '[예뻐너] 여성 니트 가디건 - 브라운 / FREE(55-77)')
        self.assertEqual(cardigan[0]['price'], 39900)
        self.assertEqual(cardigan[0]['points'], 1570)
        self.assertTrue(cardigan[0]['available'])
        self.assertEqual(cardigan[1]['price'], 41900)
        self.assertFalse(cardigan[1]['available'])  # no stock
        self.assertEqual(cardigan[2]['name'], '[예뻐너] 여성 니트 가디건 - 블랙 / FREE(55-77)')
        self.assertEqual(self.session.option_calls[0], {
            'gs_id': '695221', 'opt_id': '브라운', 'idx': 0, 'sel_count': 2,
            'opt_title': '사이즈'})
        for call in logger.warning.call_args_list:
            self.assertNotIn('695221', str(call))

    def test_group_product_is_skipped_silently(self):
        '''Group products are showcases of products listed separately anyway'''
        self.session.views['689859'] = 'view_group.html'
        logger = MagicMock()
        products = get_aza_products('u', 'p', ['011'], logger=logger, login=self.login)
        self.assertNotIn('689859', [p['vendor_id'] for p in products])
        for call in logger.warning.call_args_list:
            self.assertNotIn('689859', str(call))
        self.assertTrue(any('689859' in str(call) for call in logger.info.call_args_list))

    def test_session_expiry_aborts_import(self):
        self.session.views['695221'] = 'view_anonymous.html'
        with self.assertRaises(AzaLoginError):
            get_aza_products('u', 'p', ['011'], logger=MagicMock(), login=self.login)

    def test_no_categories_skips_login(self):
        self.assertEqual(get_aza_products('u', 'p', [], login=self.login), [])
        self.login.assert_not_called()

    def test_only_unknown_categories(self):
        self.assertEqual(
            get_aza_products('u', 'p', ['999'], logger=MagicMock(), login=self.login), [])
        self.assertEqual(self.session.list_calls, [])
