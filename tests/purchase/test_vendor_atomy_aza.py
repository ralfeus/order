'''Tests of AtomyAza (atomyaza.co.kr) purchase order functionality.
All HTTP traffic is faked with fixtures from tests/purchase/fixtures/atomy_aza'''
from datetime import date, datetime
import json
import os
from typing import Callable, Optional, Union
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from tests import BaseTestCase, db
from app.models.address import Address
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.orders.models.order_product import OrderProductStatus
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from app.purchase.models.company import Company
from app.purchase.models.vendors.atomy_aza import (
    AtomyAza, _add_to_cart, _get_order_lines, _place_order)
from app.users.models.user import User
from common.exceptions import ProductNotAvailableError, PurchaseOrderError
from common.utils.aza import URL_BASE, AzaLoginError

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'atomy_aza')

def _fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()

def _response(text: str, url: str, status: int=200) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.json.side_effect = lambda: json.loads(text)
    response.url = url
    response.status_code = status
    response.raise_for_status.side_effect = None if status < 400 \
        else Exception(f'HTTP {status}')
    return response

Route = Union[str, Callable[[str, dict], str]]

class FakeSession:
    '''Serves fixtures by method and URL path. Records all requests'''
    def __init__(self, routes: dict[tuple[str, str], Route]):
        self.routes = routes
        self.requests: list[tuple[str, str, dict]] = []

    def _serve(self, method: str, url: str, params: dict) -> MagicMock:
        self.requests.append((method, url, params))
        route = self.routes.get((method, urlparse(url).path))
        if route is None:
            raise AssertionError(f'Unexpected request {method} {url}')
        text = route(url, params) if callable(route) else _fixture(route)
        return _response(text, url)

    def get(self, url, params=None, timeout=None, **_kwargs):
        if params:
            url += ('&' if '?' in url else '?') + '&'.join(f'{k}={v}' for k, v in params.items())
        return self._serve('GET', url, dict(params or {}))

    def post(self, url, data=None, headers=None, timeout=None, **_kwargs):
        return self._serve('POST', url, _as_dict(data))

    def posted(self, path: str) -> list[dict]:
        return [data for method, url, data in self.requests
                if method == 'POST' and urlparse(url).path == path]

def _as_dict(data) -> dict:
    '''Form data as dict of lists (fields can repeat)'''
    result: dict[str, list] = {}
    for key, value in (data.items() if isinstance(data, dict) else data or []):
        result.setdefault(key, []).append(value)
    return result


def _register_sqlite_lock_functions(get_lock: Callable=lambda name, timeout: 1,
                                    release_lock: Callable=lambda name: 1):
    '''MySQL named lock functions for SQLite (session and engine share connection)'''
    with db.engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        raw.create_function('GET_LOCK', 2, get_lock)
        raw.create_function('RELEASE_LOCK', 1, release_lock)


class AzaTestCase(BaseTestCase):
    '''Order of AtomyAza products with purchase order data'''
    def setUp(self):
        super().setUp()
        db.create_all()
        _register_sqlite_lock_functions()
        self.user = User(username='user_aza', email='u@name.com', password_hash='', enabled=True)
        self.address = Address(name='Office', zip='03733', address_1='Seoul, Street 17',
                               address_2='Building 108, 504')
        self.company = Company(name='Company', phone='010-6285-2045', bank_id='06',
                               tax_id_1='123', tax_id_2='45', tax_id_3='67890',
                               address=self.address)
        self.order = Order(user=self.user)
        self.try_add_entities([
            self.user, self.address, self.company, self.order,
            Product(id='100001:4541550', vendor='AtomyAza', name='Apple small', price=27900),
            Product(id='100001:4541551', vendor='AtomyAza', name='Apple mid', price=34900),
            Product(id='100001:4541554', vendor='AtomyAza', name='Apple big', price=47900),
            Product(id='100001:9999999', vendor='AtomyAza', name='Apple gone', price=1),
            Product(id='100002', vendor='AtomyAza', name='Soup', price=30900),
            Product(id='100003', vendor='AtomyAza', name='No options', price=1000),
        ])
        self.suborder = Suborder(order=self.order, subcustomer=Subcustomer(),
                                 buyout_date=datetime(2026, 10, 17))
        self.try_add_entity(self.suborder)

    def _op(self, product_id: str, quantity: int=1) -> OrderProduct:
        op = OrderProduct(suborder=self.suborder, product_id=f'AtomyAza:{product_id}',
                          quantity=quantity)
        self.try_add_entity(op)
        return op

    def _po(self) -> PurchaseOrder:
        po = PurchaseOrder(suborder=self.suborder, address=self.address, company=self.company,
                           contact_phone='010-1111-2222', payment_phone='010-6285-2045')
        self.try_add_entity(po)
        return po


class TestAtomyAzaClient(AzaTestCase):
    # --- cart -------------------------------------------------------------

    def _view_session(self, view: str='view_options.html', cartsave: Route=lambda u, p: ''):
        return FakeSession({
            ('GET', '/m/shop/view.php'): view,
            ('POST', '/shop/ajax.cartsave.php'): cartsave,
        })

    def test_add_to_cart_option(self):
        session = self._view_session()
        _add_to_cart(session, self._op('100001:4541550', 2))
        self.assertEqual(session.requests[0][2], {'gs_id': '100001'})
        self.assertEqual(session.posted('/shop/ajax.cartsave.php'), [{
            'gs_id[]': ['100001'],
            'ca_id': ['007008012001'],
            'sw_direct': [''],
            'io_type[100001][]': ['0'],
            'io_id[100001][]': ['사과 2kg, 소과'],
            'io_no[100001][]': ['4541550'],
            'io_value[100001][]': ['옵션선택:사과 2kg, 소과'],
            'ct_qty[100001][]': ['2'],
        }])

    def test_add_to_cart_single_option_product(self):
        '''Product with single option is stored without option ID'''
        session = self._view_session('view_single_option.html')
        _add_to_cart(session, self._op('100002'))
        data = session.posted('/shop/ajax.cartsave.php')[0]
        self.assertEqual(data['io_no[100002][]'], ['4418146'])
        self.assertEqual(data['io_id[100002][]'], ['된장국 500g 10팩'])

    def test_add_to_cart_unavailable(self):
        for product_id, quantity in [
                ('100001:4541554', 1),  # not possible to buy
                ('100001:4541551', 2),  # only 1 in stock
                ('100001:9999999', 1),  # option is gone
                ('100003', 1)]:         # no options (unsupported)
            with self.subTest(product_id):
                session = self._view_session(
                    'view_no_options.html' if product_id == '100003' else 'view_options.html')
                with self.assertRaises(ProductNotAvailableError) as ctx:
                    _add_to_cart(session, self._op(product_id, quantity))
                self.assertEqual(ctx.exception.product_id, product_id)
                self.assertEqual(session.posted('/shop/ajax.cartsave.php'), [])

    def test_add_to_cart_discontinued(self):
        '''Product page of discontinued product is an alert only.
        Only the product is unavailable, not the whole purchase order'''
        session = self._view_session('view_discontinued.html')
        with self.assertRaises(ProductNotAvailableError) as ctx:
            _add_to_cart(session, self._op('100001:4541550', 1))
        self.assertEqual(ctx.exception.product_id, '100001:4541550')
        self.assertIn('현재 판매가능한 상품이 아닙니다', str(ctx.exception))
        self.assertEqual(session.posted('/shop/ajax.cartsave.php'), [])

    def test_add_to_cart_single_option_requires_no_option_id(self):
        '''Product with several options must refer to one of them'''
        self.try_add_entity(Product(id='100001', vendor='AtomyAza', name='Apple', price=1))
        with self.assertRaises(ProductNotAvailableError):
            _add_to_cart(self._view_session(), self._op('100001'))

    def test_add_to_cart_site_error(self):
        session = self._view_session(cartsave=lambda u, p: '재고가 부족합니다.')
        with self.assertRaises(ProductNotAvailableError) as ctx:
            _add_to_cart(session, self._op('100001:4541550'))
        self.assertIn('재고가 부족합니다.', str(ctx.exception))

    def test_add_to_cart_anonymous(self):
        with self.assertRaises(AzaLoginError):
            _add_to_cart(self._view_session('view_anonymous.html'), self._op('100002'))

    # --- order ------------------------------------------------------------

    def _order_session(self, orderformupdate: Route='orderformupdate.json',
                       view: str='order_view.html', cart: str='cart.html',
                       orderform: Route='orderform.html',
                       cartupdate: Route='cartupdate_buy.json',
                       orderformresult: Route='orderformresult.html'):
        return FakeSession({
            ('GET', '/m/shop/cart.php'): cart,
            # Cart is updated by AJAX. Response tells where to go next
            ('POST', '/m/shop/cartupdate.php'): cartupdate,
            ('GET', '/m/shop/orderform.php'): orderform,
            # Order is submitted by AJAX. Response tells where to go next
            ('POST', '/shop/orderformupdate.php'): orderformupdate,
            # Page submitting the virtual account request form by itself
            ('GET', '/shop/toss/virtualAccount.php'): 'virtual_account.html',
            ('POST', '/m/shop/orderformresult.php'): orderformresult,
            ('GET', '/m/shop/orderinquiryview.php'): view,
        })

    def test_place_order(self):
        session = self._order_session()
        result = _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertEqual(result, {
            'vendor_po': '26101803073003',
            'payment_account': '국민은행 50789073464931',
            'total_price': 30900
        })
        buy = session.posted('/m/shop/cartupdate.php')[0]
        self.assertEqual(buy['act'], ['buy'])
        # Only ordered products are bought. Others in the cart aren't ours
        self.assertEqual(buy['ct_chk[1]'], ['1'])
        self.assertNotIn('ct_chk[0]', buy)
        self.assertNotIn('ct_all', buy)
        data = session.posted('/shop/orderformupdate.php')[0]
        expected = {
            'ss_cart_id': ['2610180001'], 'tot_price': ['30900'], 'cart_id[0]': ['777000111'],
            'baesong_chk[]': ['0||100002'],
            'sales_date': ['2026-10-17'],
            'ad_sel_addr': ['2'],
            'b_name': ['Company 0001'], 'b_cellphone': ['01011112222'],
            'b_zip': ['03733'], 'b_addr1': ['Seoul, Street 17'],
            'b_addr2': ['Building 108, 504'], 'b_addr3': [''],
            'paymethod': ['가상계좌'],
            'virtualAcc_code': ['004'], 'virtualAcc_hp': ['01062852045'],
            'taxsave_yes': ['S'], 'tax_saupja_no': ['1234567890'],
            'sel_memo': [''], 'memo': [''], 'info_receive_yes': ['Y'],
            'cardInstallmentPlan': ['0'],
        }
        for key, value in expected.items():
            self.assertEqual(data.get(key), value, key)
        self.assertNotIn('disabled_field', data)
        self.assertNotIn('addr_add', data)
        self.assertEqual(session.posted('/m/shop/orderformresult.php')[0]['od_id'],
                         ['26101803073003'])

    def test_place_order_cart_update_error(self):
        session = self._order_session(
            cartupdate=lambda u, p: '{"code":0,"error":"주문할 수 없는 상품입니다."}')
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertIn('주문할 수 없는 상품입니다.', str(ctx.exception))
        self.assertEqual(session.posted('/shop/orderformupdate.php'), [])

    def test_place_order_no_tax_id(self):
        self.company.tax_id_1 = self.company.tax_id_2 = self.company.tax_id_3 = None
        session = self._order_session()
        _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        data = session.posted('/shop/orderformupdate.php')[0]
        self.assertEqual(data['taxsave_yes'], ['N'])
        self.assertEqual(data['tax_saupja_no'], [''])

    def test_place_order_without_purchase_date_takes_default(self):
        self.suborder.buyout_date = None
        session = self._order_session()
        _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertEqual(session.posted('/shop/orderformupdate.php')[0]['sales_date'],
                         ['2026-10-17'])

    def test_place_order_sales_date_not_available(self):
        self.suborder.buyout_date = datetime(2026, 10, 18)
        session = self._order_session()
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertIn('2026-10-18', str(ctx.exception))
        self.assertEqual(session.posted('/shop/orderformupdate.php'), [])

    def test_place_order_unsupported_bank(self):
        self.company.bank_id = 'ST'
        with self.assertRaises(PurchaseOrderError):
            _place_order(self._order_session(), self._po(), 'Company 0001', {'100002': 1})

    def test_place_order_product_not_in_cart(self):
        for cart in ['cart_empty.html', 'cart.html']:
            with self.subTest(cart):
                session = self._order_session(cart=cart)
                with self.assertRaises(PurchaseOrderError) as ctx:
                    _place_order(session, self._po(), 'Company 0001',
                                 {'100002': 1, '100009': 1})
                self.assertIn('100009', str(ctx.exception.message))
                self.assertEqual(session.posted('/m/shop/cartupdate.php'), [])

    def test_place_order_form_mismatch(self):
        foreign_line = lambda u, p: _fixture('orderform.html').replace(
            '<input type="radio" name="sales_date"',
            '<input type="hidden" name="gs_id[1]" value="100001">'
            '<input type="hidden" name="sum_qty[1]" value="1">'
            '<input type="radio" name="sales_date"', 1)
        for orderform, quantities in [
                (foreign_line, {'100002': 1}),       # product of another posting
                ('orderform.html', {'100002': 2}),   # quantity merged with another posting
                ('orderform.html', {'100002': 1, '100001': 1})]:  # product is missing
            with self.subTest(quantities):
                session = self._order_session(orderform=orderform)
                with self.assertRaises(PurchaseOrderError) as ctx:
                    _place_order(session, self._po(), 'Company 0001', quantities)
                self.assertTrue(ctx.exception.retry)
                self.assertEqual(session.posted('/shop/orderformupdate.php'), [])

    def test_place_order_site_alert(self):
        session = self._order_session(orderformupdate=lambda u, p: _fixture('alert.html'))
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertIn('재고가 부족합니다', str(ctx.exception))

    def test_place_order_error(self):
        session = self._order_session(
            orderformupdate=lambda u, p: '{"error":"재고가 부족합니다."}')
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertIn('재고가 부족합니다', str(ctx.exception))
        self.assertEqual(session.posted('/m/shop/orderformresult.php'), [])

    def test_place_order_failure_reason(self):
        session = self._order_session(orderformresult=lambda u, p:
            f"<script>location.replace('{URL_BASE}/m/shop/orderinquiryview.php"
            "?od_id=&orderformresult=0&result_reason=가상계좌 발급 실패');</script>")
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001', {'100002': 1})
        self.assertIn('가상계좌 발급 실패', str(ctx.exception))

    # --- order history ----------------------------------------------------

    def test_get_order_lines(self):
        session = FakeSession({('GET', '/m/shop/orderinquiry.php'): 'orderinquiry.html'})
        lines = _get_order_lines(session, date(2026, 9, 1), date(2026, 10, 18))
        # Without the full set of search form fields the site ignores the dates
        # and shows the last week only
        self.assertEqual(session.requests[0][2], {
            'dtbtnval': '', 'shop_table_name': 'shop_order', 'mng_method': '',
            'date_period': '', 'fr_date': '2026-09-01', 'to_date': '2026-10-18', 'gname': ''})
        self.assertEqual(lines, [
            {'id': '26091400270072', 'gs_id': '651536', 'status_code': 5, 'quantity': 1},
            {'id': '26091400270072', 'gs_id': '651537', 'status_code': 4, 'quantity': 3},
            {'id': '26101803073003', 'gs_id': '651536', 'status_code': 6, 'quantity': 1},
        ])

    def test_get_order_lines_empty(self):
        session = FakeSession({('GET', '/m/shop/orderinquiry.php'): 'orderinquiry_empty.html'})
        self.assertEqual(_get_order_lines(session, date(2026, 9, 1), date(2026, 10, 18)), [])

    def test_get_order_lines_anonymous(self):
        session = FakeSession({('GET', '/m/shop/orderinquiry.php'): 'view_anonymous.html'})
        with self.assertRaises(AzaLoginError):
            _get_order_lines(session, date(2026, 9, 1), date(2026, 10, 18))


MODULE = 'app.purchase.models.vendors.atomy_aza'
CONFIG = {'AZA_LOGIN': 'company', 'AZA_PASSWORD': 'secret', 'AZA_SOCKS5_PROXY': '',
          'ATOMY_RECEIVER_NAME_FORMAT': '{company} {id1}', 'LOG_LEVEL': 'INFO'}
ORDER_DETAILS = {'vendor_po': '26101803073003', 'payment_account': '국민은행 50789073464931',
                 'total_price': 61800}

class TestAtomyAzaVendor(AzaTestCase):
    def setUp(self):
        super().setUp()
        self.ops = [self._op('100001:4541550', 1), self._op('100002', 1)]
        self.po = self._po()
        patches = {
            'login': patch(f'{MODULE}.aza_login', return_value='session'),
            'add': patch(f'{MODULE}._add_to_cart'),
            'place': patch(f'{MODULE}._place_order', return_value=dict(ORDER_DETAILS)),
            'lines': patch(f'{MODULE}._get_order_lines', return_value=[]),
        }
        self.mocks = {name: p.start() for name, p in patches.items()}
        for p in patches.values():
            self.addCleanup(p.stop)
        self.vendor = AtomyAza(config=CONFIG)

    def test_post_purchase_order(self):
        po, unavailable = self.vendor.post_purchase_order(self.po)
        self.assertEqual(unavailable, {})
        self.mocks['login'].assert_called_once_with('company', 'secret', '')
        self.assertEqual([c.args[1] for c in self.mocks['add'].call_args_list], self.ops)
        session, placed_po, receiver, quantities = self.mocks['place'].call_args.args
        self.assertIs(placed_po, self.po)
        self.assertEqual(quantities, {'100001': 1, '100002': 1})
        self.assertEqual(receiver, f"Company {self.po.id[8:].split('-')[1]}")
        self.assertEqual((po.vendor_po_id, po.payment_account, po.total_krw),
                         ('26101803073003', '국민은행 50789073464931', 61800))
        self.assertEqual([op.status for op in self.ops], [OrderProductStatus.purchased] * 2)

    def test_post_purchase_order_quantities_by_product(self):
        '''Options of the same product are one line of the order form'''
        self.ops.append(self._op('100001:4541551', 2))
        self.vendor.post_purchase_order(self.po)
        self.assertEqual(self.mocks['place'].call_args.args[3], {'100001': 3, '100002': 1})

    def test_post_purchase_order_holds_account_lock(self):
        calls = []
        def place(*_args):
            calls.append('place')
            return dict(ORDER_DETAILS)
        self.mocks['place'].side_effect = place
        _register_sqlite_lock_functions(
            lambda name, timeout: calls.append(('get', name, timeout)) or 1,
            lambda name: calls.append(('release', name)) or 1)
        self.vendor.post_purchase_order(self.po)
        self.assertEqual(calls, [('get', 'po_posting:aza:company', 300), 'place',
                                 ('release', 'po_posting:aza:company')])

    def test_post_purchase_order_releases_lock_on_failure(self):
        released = []
        _register_sqlite_lock_functions(release_lock=lambda name: released.append(name) or 1)
        self.mocks['place'].side_effect = PurchaseOrderError(message='Failed')
        with self.assertRaises(PurchaseOrderError):
            self.vendor.post_purchase_order(self.po)
        self.assertEqual(released, ['po_posting:aza:company'])

    def test_post_purchase_order_account_busy(self):
        _register_sqlite_lock_functions(get_lock=lambda name, timeout: 0)
        with self.assertRaises(PurchaseOrderError) as ctx:
            self.vendor.post_purchase_order(self.po)
        self.assertIn('in progress', str(ctx.exception))
        self.mocks['add'].assert_not_called()
        self.mocks['place'].assert_not_called()

    def test_post_purchase_order_unavailable_product(self):
        def add(_session, op):
            if op.product_id == '100002':
                raise ProductNotAvailableError('100002', 'Sold out')
        self.mocks['add'].side_effect = add
        _po, unavailable = self.vendor.post_purchase_order(self.po)
        self.assertEqual(unavailable, {'100002': 'Sold out'})
        self.mocks['place'].assert_called_once()
        self.assertEqual([op.status for op in self.ops],
                         [OrderProductStatus.purchased, OrderProductStatus.pending])

    def test_post_purchase_order_no_products_available(self):
        self.mocks['add'].side_effect = ProductNotAvailableError('x', 'Sold out')
        with self.assertRaises(PurchaseOrderError):
            self.vendor.post_purchase_order(self.po)
        self.mocks['place'].assert_not_called()

    def test_post_purchase_order_skips_exempted_products(self):
        self.ops[0].product.purchase = False
        self.ops[1].quantity = 0
        with self.assertRaises(PurchaseOrderError):
            self.vendor.post_purchase_order(self.po)
        self.mocks['add'].assert_not_called()

    def test_post_purchase_order_login_failure(self):
        self.mocks['login'].side_effect = AzaLoginError('Wrong password')
        with self.assertRaises(PurchaseOrderError) as ctx:
            self.vendor.post_purchase_order(self.po)
        self.assertIn('Wrong password', str(ctx.exception))

    def test_post_purchase_order_no_credentials(self):
        vendor = AtomyAza(config={**CONFIG, 'AZA_LOGIN': ''})
        with self.assertRaises(PurchaseOrderError) as ctx:
            vendor.post_purchase_order(self.po)
        self.assertIn('AZA_LOGIN', str(ctx.exception))
        self.mocks['login'].assert_not_called()

    def test_post_purchase_order_network_error(self):
        import requests
        self.mocks['place'].side_effect = requests.ConnectionError('Connection reset')
        with self.assertRaises(PurchaseOrderError) as ctx:
            self.vendor.post_purchase_order(self.po)
        self.assertIn('Connection reset', str(ctx.exception))

    def test_session_is_reused(self):
        self.vendor.post_purchase_order(self.po)
        self.vendor.post_purchase_order(self.po)
        self.mocks['login'].assert_called_once()

    def _update(self, *lines: tuple[int, ...]) -> PurchaseOrder:
        self.po.vendor_po_id = '26101803073003'
        self.po.status = PurchaseOrderStatus.posted
        self.mocks['lines'].return_value = [
            {'id': '26101803073003', 'gs_id': str(i), 'status_code': code, 'quantity': 1}
            for i, code in enumerate(lines)] + [
            {'id': '99999999999999', 'gs_id': '1', 'status_code': 5, 'quantity': 1}]
        self.vendor.update_purchase_orders_status(self.po.customer, [self.po])
        return self.po

    def test_update_status(self):
        for codes, status in [
                ((1,), PurchaseOrderStatus.posted),
                ((2,), PurchaseOrderStatus.paid),
                ((3,), PurchaseOrderStatus.paid),
                ((4,), PurchaseOrderStatus.shipped),
                ((5,), PurchaseOrderStatus.delivered),
                ((6,), PurchaseOrderStatus.cancelled),
                ((6, 6), PurchaseOrderStatus.cancelled),
                ((5, 6), PurchaseOrderStatus.delivered),  # partially cancelled
                ((5, 3), PurchaseOrderStatus.paid),       # least advanced item decides
                ((4, 5), PurchaseOrderStatus.shipped)]:
            with self.subTest(codes):
                self.assertEqual(self._update(*codes).status, status)

    def test_update_status_takes_no_lock(self):
        _register_sqlite_lock_functions(
            get_lock=lambda name, timeout: (_ for _ in ()).throw(AssertionError('locked')))
        self._update(2)

    def test_update_status_period(self):
        self.po.when_created = datetime(2026, 10, 10, 15, 0)
        self._update(2)
        from_date, to_date = self.mocks['lines'].call_args.args[1:]
        self.assertEqual(from_date, date(2026, 10, 9))
        self.assertEqual(to_date, date.today())

    def test_update_status_unknown_code_keeps_status(self):
        self.assertEqual(self._update(9).status, PurchaseOrderStatus.posted)

    def test_update_status_not_found_keeps_status(self):
        self.po.vendor_po_id = 'other'
        self.mocks['lines'].return_value = [
            {'id': '26101803073003', 'gs_id': '1', 'status_code': 5, 'quantity': 1}]
        self.vendor.update_purchase_orders_status(self.po.customer, [self.po])
        self.assertEqual(self.po.status, None)

    def test_update_status_unchanged_isnt_set(self):
        with patch.object(PurchaseOrder, 'set_status') as set_status:
            self._update(1)
        set_status.assert_not_called()
