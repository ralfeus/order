'''Manages purchase orders at AtomyAza (atomyaza.co.kr).
Orders are placed with the company account via plain HTTP requests:
cart -> order form -> virtual account payment'''
from contextlib import contextmanager
from datetime import date, timedelta
import logging
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
import requests
from sqlalchemy import text

from app import db
from app.orders.models.order_product import OrderProduct, OrderProductStatus
from app.orders.models.subcustomer import Subcustomer
from app.purchase.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from common.exceptions import ProductNotAvailableError, PurchaseOrderError
from common.utils.aza import TIMEOUT, URL_BASE, AzaLoginError, aza_login
from .atomy_quick import get_receiver_name
from .vendor_base import PurchaseOrderVendorBase

# Company bank IDs (see companies.js) to AtomyAza virtual account bank codes
BANK_CODES = {
    '03': '003', # IBK기업은행
    '06': '004', # KB국민은행
    '07': '007', # Sh수협은행
    '11': '011', # NH농협은행
    '20': '020', # 우리은행
    '31': '031', # DGB대구은행
    '32': '032', # 부산은행
    '34': '034', # 광주은행
    '39': '039', # 경남은행
    '71': '071', # 우체국
    '81': '081', # 하나은행
    '88': '088', # 신한은행
}
PAYMENT_METHOD = '가상계좌'
NEW_ADDRESS = '2'
CASH_RECEIPT_NONE = 'N'
CASH_RECEIPT_BUSINESS = 'S'
MAX_REDIRECTS = 5
LOCK_TIMEOUT = 300
# Order item status codes (em.dan_nm<code>) of the order history
ORDER_STATUSES = {
    1: PurchaseOrderStatus.posted,    # 입금대기
    2: PurchaseOrderStatus.paid,      # 결제완료
    3: PurchaseOrderStatus.paid,      # 배송준비
    4: PurchaseOrderStatus.shipped,   # 배송중
    5: PurchaseOrderStatus.delivered, # 배송완료
    6: PurchaseOrderStatus.cancelled, # 취소완료
}
STATUS_PROGRESS = [PurchaseOrderStatus.posted, PurchaseOrderStatus.paid,
                   PurchaseOrderStatus.shipped, PurchaseOrderStatus.delivered]

_ALERT = re.compile(
    r'''alert\(\s*(["'])(?P<message>.*?)\1\s*\)\s*;?\s*'''
    r'''(history\.(back|go)|(window\.|document\.)?location)''', re.S)
_SCRIPT_REDIRECT = re.compile(
    r'''location(\.href)?\s*(=|\.replace\(|\.assign\()\s*(["'])(?P<url>[^"']+)\3''')
_META_REDIRECT = re.compile(r'''url\s*=\s*['"]?(?P<url>[^'">\s]+)''', re.I)

def _get(session: requests.Session, url: str, params: Optional[dict[str, str]]=None
         ) -> requests.Response:
    response = session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return _follow(session, response)

def _post(session: requests.Session, url: str, data: Any,
          headers: Optional[dict[str, str]]=None) -> requests.Response:
    response = session.post(url, data=data, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return _follow(session, response)

def _follow(session: requests.Session, response: requests.Response) -> requests.Response:
    '''Checks the page for login and site errors and follows redirects
    made by script or meta refresh (HTTP redirects are followed by requests)'''
    for _ in range(MAX_REDIRECTS):
        text = response.text
        if re.search(r'tb_is_member\s*=\s*"0"', text):
            raise AzaLoginError("AtomyAza session isn't authenticated")
        doc = BeautifulSoup(text, 'html.parser')
        # Pages with content have alerts and redirects in their scripts too
        if doc.select_one('form, section, ul, dl'):
            return response
        alert = _ALERT.search(text)
        if alert:
            raise PurchaseOrderError(message=alert.group('message'))
        redirect = _get_redirect(doc, text)
        if redirect is None:
            return response
        response = session.get(urljoin(response.url, redirect), timeout=TIMEOUT)
        response.raise_for_status()
    raise PurchaseOrderError(message=f"Too many redirects at {response.url}")

def _ajax_post(session: requests.Session, url: str, data: Any) -> requests.Response:
    '''Posts a form the way site's scripts do. The response is JSON with
    the next page URL or an error. Then goes to the next page'''
    response = session.post(url, data=data, headers={'X-Requested-With': 'XMLHttpRequest'},
                            timeout=TIMEOUT)
    response.raise_for_status()
    try:
        result = response.json()
    except ValueError:
        # Not JSON - an error page
        return _follow(session, response)
    if result.get('error') or not result.get('url'):
        raise PurchaseOrderError(message=result.get('error') or
                                 f"Unexpected response at {url}: {result}")
    return _get(session, urljoin(url, result['url']))

def _get_redirect(doc: BeautifulSoup, text: str) -> Optional[str]:
    '''Returns target URL of a page that only redirects'''
    meta = doc.select_one('meta[http-equiv="refresh" i]')
    if meta and _META_REDIRECT.search(str(meta.get('content', ''))):
        return _META_REDIRECT.search(str(meta['content'])).group('url') #type: ignore
    match = _SCRIPT_REDIRECT.search(text)
    return match.group('url') if match else None

def _form_fields(form: Tag) -> list[tuple[str, str]]:
    '''Serializes the form like a browser does'''
    fields = []
    for element in form.select('input, select, textarea'):
        name = element.get('name')
        if not name or element.has_attr('disabled'):
            continue
        if element.name == 'select':
            option = element.select_one('option[selected]') or element.select_one('option')
            fields.append((str(name), str(option.get('value', option.get_text())) if option else ''))
        elif element.name == 'textarea':
            fields.append((str(name), element.get_text()))
        else:
            input_type = str(element.get('type', 'text')).lower()
            if input_type in ('submit', 'button', 'image', 'file', 'reset'):
                continue
            if input_type in ('checkbox', 'radio') and not element.has_attr('checked'):
                continue
            fields.append((str(name), str(element.get('value', 'on'))))
    return fields

def _set_field(fields: list[tuple[str, str]], name: str, value: str) -> None:
    '''Sets the single value of the field'''
    fields[:] = [field for field in fields if field[0] != name] + [(name, value)]

def _digits(text: Optional[str]) -> str:
    return re.sub(r'\D', '', text or '')

def _get_form(response: requests.Response, selector: str) -> Tag:
    form = BeautifulSoup(response.text, 'html.parser').select_one(selector)
    if form is None:
        raise PurchaseOrderError(message=f"No form <{selector}> at {response.url}")
    return form

def _get_option(doc: BeautifulSoup, product_id: str, option_id: Optional[str]
                ) -> dict[str, Any]:
    '''Returns the option to be ordered. Option's data-value is
    "name,additional price,stock,base price,PV,option ID"'''
    options = []
    for li in doc.select('li.opt_list_li[data-value]'):
        name, _add_price, stock, _price, _points, number = \
            str(li['data-value']).rsplit(',', 5)
        options.append({'name': name, 'number': number.strip(), 'stock': int(stock),
                        'possible': li.get('data-possible') == '1'})
    if len(options) == 0:
        # Cart payload for products without options wasn't observed yet
        raise ProductNotAvailableError(product_id, "Products without options aren't supported")
    if option_id is None:
        if len(options) > 1:
            raise ProductNotAvailableError(product_id, "Product option isn't specified")
        return options[0]
    option = next((o for o in options if o['number'] == option_id), None)
    if option is None:
        raise ProductNotAvailableError(product_id, "Product option doesn't exist")
    return option

def _add_to_cart(session: requests.Session, order_product: OrderProduct) -> None:
    '''Adds the order product to the cart.
    Raises ProductNotAvailableError if the product can't be added'''
    product_id = str(order_product.product_id)
    gs_id, _, option_id = product_id.partition(':')
    try:
        response = _get(session, f'{URL_BASE}/m/shop/view.php', params={'gs_id': gs_id})
    except PurchaseOrderError as ex:
        # Discontinued product's page is an alert only
        raise ProductNotAvailableError(product_id, ex.message) from ex
    doc = BeautifulSoup(response.text, 'html.parser')
    ca_id = doc.select_one('form[name="fbuyform"] input[name="ca_id"]')
    if ca_id is None:
        raise ProductNotAvailableError(product_id, "Product page has no purchase form")
    option = _get_option(doc, product_id, option_id or None)
    if not option['possible'] or option['stock'] < order_product.quantity:
        raise ProductNotAvailableError(product_id, f"Only {option['stock']} available"
                                       if option['possible'] else "Sold out")
    response = session.post(f'{URL_BASE}/shop/ajax.cartsave.php', data=[
        ('gs_id[]', gs_id),
        ('ca_id', str(ca_id.get('value', ''))),
        ('sw_direct', ''),
        (f'io_type[{gs_id}][]', '0'),
        (f'io_id[{gs_id}][]', option['name']),
        (f'io_no[{gs_id}][]', option['number']),
        (f'io_value[{gs_id}][]', f"옵션선택:{option['name']}"),
        (f'ct_qty[{gs_id}][]', str(order_product.quantity)),
    ], headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=TIMEOUT)
    response.raise_for_status()
    # Empty response means success. Otherwise it's an error message
    if response.text.strip():
        raise ProductNotAvailableError(product_id, response.text.strip())

def _buy_cart_products(session: requests.Session, gs_ids: set[str]) -> requests.Response:
    '''Proceeds to the order form with the provided products of the cart.
    Other products in the cart are left intact as the account can be shared'''
    response = _get(session, f'{URL_BASE}/m/shop/cart.php')
    form = _get_form(response, 'form[name="frmcartlist"]')
    rows = {str(row.get('value')): str(row['name']).replace('gs_id', 'ct_chk', 1)
            for row in form.select('input[name^="gs_id["]')}
    missing = gs_ids - rows.keys()
    if missing:
        raise PurchaseOrderError(message=f"Products {sorted(missing)} aren't in the cart")
    fields = [field for field in _form_fields(form)
              if not field[0].startswith('ct_chk[') and field[0] != 'ct_all']
    fields += [(rows[gs_id], '1') for gs_id in sorted(gs_ids)]
    _set_field(fields, 'act', 'buy')
    return _ajax_post(session, urljoin(response.url, str(form.get('action', ''))), fields)

def _check_order_form(form: Tag, quantities: dict[str, int],
                      purchase_order: PurchaseOrder) -> None:
    '''Ensures the order form has exactly the products to be ordered.
    Anything else got to the cart from another posting with the same account'''
    lines: dict[str, int] = {}
    for gs_id in form.select('input[name^="gs_id["]'):
        quantity = form.select_one(
            f'input[name="{str(gs_id["name"]).replace("gs_id", "sum_qty", 1)}"]')
        value = _digits(str(quantity.get('value', ''))) if quantity is not None else ''
        lines[str(gs_id.get('value'))] = \
            lines.get(str(gs_id.get('value')), 0) + int(value or 0)
    if lines != quantities:
        raise PurchaseOrderError(purchase_order, message=
            f"Order form products {lines} don't match ordered ones {quantities}", retry=True)

def _place_order(session: requests.Session, purchase_order: PurchaseOrder,
                 receiver_name: str, quantities: dict[str, int]) -> dict[str, Any]:
    '''Orders the products of the cart with virtual account payment.
    :param quantities: quantities of the products to be ordered by gs_id
    Returns vendor's order ID, payment account and total price'''
    response = _buy_cart_products(session, set(quantities))
    form = _get_form(response, 'form[action*="orderformupdate"]')
    _check_order_form(form, quantities, purchase_order)
    fields = _form_fields(form)

    sales_dates = [str(r['value']) for r in form.select('input[name="sales_date"]')]
    sales_date = purchase_order.purchase_date.isoformat() if purchase_order.purchase_date \
        else dict(fields).get('sales_date', '')
    if sales_date not in sales_dates:
        raise PurchaseOrderError(purchase_order, message=
            f"Sales date {sales_date} isn't available. Available dates are {sales_dates}")
    bank_code = BANK_CODES.get(str(purchase_order.company.bank_id))
    if bank_code is None:
        raise PurchaseOrderError(purchase_order, message=
            f"Bank {purchase_order.company.bank_id} isn't supported by AtomyAza")
    business_number = ''.join(part or '' for part in purchase_order.company.tax_id)
    address = purchase_order.address
    for name, value in {
        'sales_date': sales_date,
        'ad_sel_addr': NEW_ADDRESS,
        'b_name': receiver_name,
        'b_cellphone': _digits(purchase_order.contact_phone),
        'b_zip': address.zip,
        'b_addr1': address.address_1,
        'b_addr2': address.address_2 or '',
        'b_addr3': '',
        'paymethod': PAYMENT_METHOD,
        'virtualAcc_code': bank_code,
        'virtualAcc_hp': _digits(purchase_order.payment_phone),
        'taxsave_yes': CASH_RECEIPT_BUSINESS if business_number else CASH_RECEIPT_NONE,
        'tax_saupja_no': business_number,
    }.items():
        _set_field(fields, name, value)

    response = _ajax_post(session, urljoin(response.url, str(form.get('action', ''))), fields)
    # Virtual account is requested by the form the page submits by itself
    form = BeautifulSoup(response.text, 'html.parser').select_one('form#forderform')
    if form is not None:
        response = _post(session, urljoin(response.url, str(form.get('action', ''))),
                         _form_fields(form))
    query = parse_qs(urlparse(response.url).query)
    order_id = query.get('od_id', [''])[0]
    if not urlparse(response.url).path.endswith('orderinquiryview.php') or not order_id:
        raise PurchaseOrderError(purchase_order, message=
            query.get('result_reason', [''])[0] or f"Unexpected result page {response.url}")
    return _parse_order_details(response.text, purchase_order)

def _parse_order_details(text: str, purchase_order: PurchaseOrder) -> dict[str, Any]:
    details = {}
    for dt in BeautifulSoup(text, 'html.parser').select('section.section_order dl dt'):
        dd = dt.find_next_sibling('dd')
        if dd is not None:
            details[dt.get_text(strip=True)] = dd
    try:
        account = details['입금계좌']
        bank = account.find(string=True, recursive=False)
        return {
            'vendor_po': details['주문번호'].get_text(strip=True),
            'payment_account': f"{str(bank).strip()} " +
                account.select_one('.bank_account').get_text(strip=True), #type: ignore
            'total_price': int(_digits(details['결제금액'].get_text()))
        }
    except (KeyError, AttributeError, ValueError) as ex:
        raise PurchaseOrderError(purchase_order, message=
            f"Couldn't get the order details: {ex}") from ex

def _get_order_lines(session: requests.Session, from_date: date, to_date: date
                     ) -> list[dict[str, Any]]:
    '''Returns ordered items of the account's orders made in the period.
    Status is per item'''
    # All search form fields are needed. Otherwise the dates are ignored
    # and the last week is shown
    response = _get(session, f'{URL_BASE}/m/shop/orderinquiry.php', params={
        'dtbtnval': '',
        'shop_table_name': 'shop_order',
        'mng_method': '',
        'date_period': '',
        'fr_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
        'gname': ''
    })
    lines = []
    for order in BeautifulSoup(response.text, 'html.parser').select('li'):
        order_id = order.select_one('div.inquiry_idtime .idtime_link')
        if order_id is None:
            continue
        for item in order.select('div.inquiry_info'):
            status = item.find_previous_sibling('div', class_='inquiry_inv')
            status = status.select_one('em[class^="dan_nm"]') if status else None
            link = item.select_one('.inquiry_name a[href*="gs_id"]')
            quantity = item.select_one('.inquiry_qty')
            if status is None or link is None:
                logging.warning("Couldn't parse an item of AtomyAza order %s",
                                order_id.get_text(strip=True))
                continue
            lines.append({
                'id': order_id.get_text(strip=True),
                'gs_id': parse_qs(urlparse(str(link['href'])).query)['gs_id'][0],
                'status_code': int(_digits(' '.join(status.get('class', []))) or 0),
                'quantity': int(_digits(quantity.get_text()) or 0) if quantity else 0
            })
    return lines


@contextmanager
def _account_lock(username: str, timeout: int):
    '''Holds MySQL named lock of the AtomyAza account while its cart is used.
    Named locks are server wide, so tenants sharing the account wait for each other.
    The lock is released by MySQL if the worker dies'''
    name = f'po_posting:aza:{username}'
    with db.engine.connect() as connection:
        acquired = connection.execute(
            text("SELECT GET_LOCK(:name, :timeout)"), {'name': name, 'timeout': timeout}
        ).scalar()
        connection.commit()
        if not acquired:
            raise PurchaseOrderError(message=
                f"Another posting with AtomyAza account {username} is in progress")
        try:
            yield
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:name)"), {'name': name})
            connection.commit()


class AtomyAza(PurchaseOrderVendorBase):
    '''Manages purchase orders at AtomyAza. All orders are placed with
    the company account set by AZA_LOGIN and AZA_PASSWORD'''
    def __init__(self, browser=None, logger: Optional[logging.Logger]=None,
                 config: Optional[dict[str, Any]]=None, **_kwargs):
        super().__init__()
        if not config:
            from flask import current_app
            config = current_app.config
        self.__config: dict[str, Any] = config
        self._logger = logger or logging.getLogger(type(self).__name__)
        self.__session: Optional[requests.Session] = None

    def __str__(self):
        return "AtomyAza"

    def __get_session(self, purchase_order: Optional[PurchaseOrder]=None
                      ) -> requests.Session:
        '''Logs in once and reuses the session for all purchase orders'''
        if self.__session is None:
            username = self.__config.get('AZA_LOGIN')
            password = self.__config.get('AZA_PASSWORD')
            if not username or not password:
                raise PurchaseOrderError(purchase_order, self,
                    "AZA_LOGIN and AZA_PASSWORD must be configured")
            try:
                self.__session = aza_login(username, password,
                                           self.__config.get('AZA_SOCKS5_PROXY', ''))
            except (AzaLoginError, requests.RequestException) as ex:
                raise PurchaseOrderError(purchase_order, self,
                    f"Couldn't log in to AtomyAza: {ex}") from ex
        return self.__session

    def post_purchase_order(self, purchase_order: PurchaseOrder
                            ) -> tuple[PurchaseOrder, dict[str, str]]:
        '''Posts the purchase order to AtomyAza.
        Returns the purchase order and products that couldn't be ordered'''
        session = self.__get_session(purchase_order)
        logger = self._logger.getChild(purchase_order.id)
        try:
            with _account_lock(self.__config['AZA_LOGIN'],
                               int(self.__config.get('AZA_PO_LOCK_TIMEOUT', LOCK_TIMEOUT))):
                ordered_products, unavailable_products = \
                    self.__add_products(session, purchase_order, logger)
                if len(ordered_products) == 0:
                    raise PurchaseOrderError(purchase_order, self, "No products could be added")
                quantities: dict[str, int] = {}
                for (op,) in ordered_products:
                    gs_id = str(op.product_id).partition(':')[0]
                    quantities[gs_id] = quantities.get(gs_id, 0) + op.quantity
                receiver_name = get_receiver_name(purchase_order,
                    self.__config.get('ATOMY_RECEIVER_NAME_FORMAT', '{company} {id1}'))
                details = _place_order(session, purchase_order, receiver_name, quantities)
        except AzaLoginError as ex:
            self.__session = None
            raise PurchaseOrderError(purchase_order, self, str(ex)) from ex
        except requests.RequestException as ex:
            raise PurchaseOrderError(purchase_order, self, str(ex)) from ex
        except PurchaseOrderError as ex:
            if ex.po_id is None:
                raise PurchaseOrderError(purchase_order, self, ex.message) from ex
            raise
        logger.info("Created order %s", details['vendor_po'])
        purchase_order.vendor_po_id = details['vendor_po']
        purchase_order.payment_account = details['payment_account']
        purchase_order.total_krw = details['total_price']
        self._set_order_products_status(ordered_products, OrderProductStatus.purchased)
        return purchase_order, unavailable_products

    def __add_products(self, session: requests.Session, purchase_order: PurchaseOrder,
                       logger: logging.Logger
                       ) -> tuple[list[tuple[OrderProduct]], dict[str, str]]:
        ordered_products = []
        unavailable_products = {}
        for op in purchase_order.order_products:
            if not op.product.purchase:
                logger.warning("The product %s is exempted from purchase", op.product_id)
                continue
            if op.quantity <= 0:
                logger.warning("The product %s has wrong quantity %s",
                               op.product_id, op.quantity)
                continue
            try:
                _add_to_cart(session, op)
                ordered_products.append((op,))
                logger.info("Added product %s", op.product_id)
            except ProductNotAvailableError as ex:
                logger.warning("Product %s is not available: %s", ex.product_id, ex.message)
                unavailable_products[ex.product_id] = ex.message
        return ordered_products, unavailable_products

    def update_purchase_orders_status(self, customer: Subcustomer,
                                      customer_pos: list[PurchaseOrder]):
        '''Updates statuses of the purchase orders by AtomyAza order history.
        The customer is irrelevant as all orders are made with the company account'''
        created = [po.when_created.date() for po in customer_pos if po.when_created]
        from_date = min(created) - timedelta(days=1) if created \
            else date.today() - timedelta(weeks=1)
        # Orders are dated in Korean time, which can be the next day already
        lines = _get_order_lines(self.__get_session(), from_date,
                                 date.today() + timedelta(days=1))
        orders: dict[str, list[int]] = {}
        for line in lines:
            orders.setdefault(line['id'], []).append(line['status_code'])
        for po in customer_pos:
            codes = orders.get(str(po.vendor_po_id))
            if codes is None:
                self._logger.warning("No AtomyAza order <%s> of %s was found",
                                     po.vendor_po_id, po.id)
                continue
            status = self.__get_order_status(codes)
            if status is None:
                self._logger.warning("Unknown status codes %s of AtomyAza order <%s>",
                                     codes, po.vendor_po_id)
            elif status != po.status:
                self._logger.debug("Setting %s status to <%s>", po.id, status)
                po.set_status(status)

    @staticmethod
    def __get_order_status(codes: list[int]) -> Optional[PurchaseOrderStatus]:
        '''Order is cancelled if all its items are. Otherwise
        the least advanced of not cancelled items defines the status'''
        if any(code not in ORDER_STATUSES for code in codes):
            return None
        statuses = [ORDER_STATUSES[code] for code in codes
                    if ORDER_STATUSES[code] != PurchaseOrderStatus.cancelled]
        if len(statuses) == 0:
            return PurchaseOrderStatus.cancelled
        return min(statuses, key=STATUS_PROGRESS.index)
