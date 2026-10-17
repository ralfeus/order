'''Tests of AtomyAza (atomyaza.co.kr) purchase order functionality.
All HTTP traffic is faked with fixtures from tests/purchase/fixtures/atomy_aza'''
from datetime import date, datetime
import os
from typing import Callable, Optional, Union
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from tests import BaseTestCase, db
from app.models.address import Address
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.purchase.models import PurchaseOrder
from app.purchase.models.company import Company
from app.purchase.models.vendors.atomy_aza import (
    _add_to_cart, _clear_cart, _get_order_lines, _place_order)
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


class TestAtomyAzaClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
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

    def test_clear_cart(self):
        session = FakeSession({
            ('GET', '/m/shop/cart.php'): 'cart.html',
            ('POST', '/m/shop/cartupdate.php'): 'cart_empty.html',
        })
        _clear_cart(session)
        data = session.posted('/m/shop/cartupdate.php')[0]
        self.assertEqual(data['act'], ['alldelete'])
        self.assertEqual(data['ct_chk[0]'], ['1'])
        self.assertEqual(data['ct_chk[1]'], ['1'])
        self.assertEqual(data['gs_id[1]'], ['100002'])

    def test_clear_empty_cart(self):
        session = FakeSession({('GET', '/m/shop/cart.php'): 'cart_empty.html'})
        _clear_cart(session)
        self.assertEqual(session.posted('/m/shop/cartupdate.php'), [])

    # --- order ------------------------------------------------------------

    def _order_session(self, orderformupdate: Route=None, view: str='order_view.html',
                       cart: str='cart.html'):
        return FakeSession({
            ('GET', '/m/shop/cart.php'): cart,
            ('POST', '/m/shop/cartupdate.php'): 'script_redirect_orderform.html',
            ('GET', '/m/shop/orderform.php'): 'orderform.html',
            ('POST', '/shop/orderformupdate.php'): orderformupdate or (lambda u, p:
                f"<script>location.replace('{URL_BASE}/shop/toss/virtualAccount.php"
                "?od_id=26101803073003&tot_price=30900');</script>"),
            ('GET', '/shop/toss/virtualAccount.php'): 'virtual_account.html',
            ('GET', '/m/shop/orderinquiryview.php'): view,
        })

    def test_place_order(self):
        session = self._order_session()
        result = _place_order(session, self._po(), 'Company 0001')
        self.assertEqual(result, {
            'vendor_po': '26101803073003',
            'payment_account': '국민은행 50789073464931',
            'total_price': 30900
        })
        buy = session.posted('/m/shop/cartupdate.php')[0]
        self.assertEqual(buy['act'], ['buy'])
        self.assertEqual(buy['ct_chk[1]'], ['1'])
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

    def test_place_order_no_tax_id(self):
        self.company.tax_id_1 = self.company.tax_id_2 = self.company.tax_id_3 = None
        session = self._order_session()
        _place_order(session, self._po(), 'Company 0001')
        data = session.posted('/shop/orderformupdate.php')[0]
        self.assertEqual(data['taxsave_yes'], ['N'])
        self.assertEqual(data['tax_saupja_no'], [''])

    def test_place_order_without_purchase_date_takes_default(self):
        self.suborder.buyout_date = None
        session = self._order_session()
        _place_order(session, self._po(), 'Company 0001')
        self.assertEqual(session.posted('/shop/orderformupdate.php')[0]['sales_date'],
                         ['2026-10-17'])

    def test_place_order_sales_date_not_available(self):
        self.suborder.buyout_date = datetime(2026, 10, 18)
        session = self._order_session()
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001')
        self.assertIn('2026-10-18', str(ctx.exception))
        self.assertEqual(session.posted('/shop/orderformupdate.php'), [])

    def test_place_order_unsupported_bank(self):
        self.company.bank_id = 'ST'
        with self.assertRaises(PurchaseOrderError):
            _place_order(self._order_session(), self._po(), 'Company 0001')

    def test_place_order_empty_cart(self):
        session = self._order_session(cart='cart_empty.html')
        with self.assertRaises(PurchaseOrderError):
            _place_order(session, self._po(), 'Company 0001')
        self.assertEqual(session.posted('/m/shop/cartupdate.php'), [])

    def test_place_order_site_alert(self):
        session = self._order_session(orderformupdate=lambda u, p: _fixture('alert.html'))
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001')
        self.assertIn('재고가 부족합니다', str(ctx.exception))

    def test_place_order_failure_reason(self):
        session = self._order_session(orderformupdate=lambda u, p:
            f"<script>location.replace('{URL_BASE}/m/shop/orderinquiryview.php"
            "?od_id=&orderformresult=0&result_reason=가상계좌 발급 실패');</script>")
        with self.assertRaises(PurchaseOrderError) as ctx:
            _place_order(session, self._po(), 'Company 0001')
        self.assertIn('가상계좌 발급 실패', str(ctx.exception))

    # --- order history ----------------------------------------------------

    def test_get_order_lines(self):
        session = FakeSession({('GET', '/m/shop/orderinquiry.php'): 'orderinquiry.html'})
        lines = _get_order_lines(session, date(2026, 9, 1), date(2026, 10, 18))
        params = session.requests[0][2]
        self.assertEqual((params['fr_date'], params['to_date'], params['shop_table_name']),
                         ('2026-09-01', '2026-10-18', 'shop_order'))
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
