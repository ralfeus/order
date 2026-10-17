'''Manages purchase orders at AtomyAza (atomyaza.co.kr).
Orders are placed with the company account via plain HTTP requests:
cart -> order form -> virtual account payment'''
from datetime import date
import logging
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
import requests

from app.orders.models.order_product import OrderProduct
from app.purchase.models.purchase_order import PurchaseOrder
from common.exceptions import ProductNotAvailableError, PurchaseOrderError
from common.utils.aza import TIMEOUT, URL_BASE, AzaLoginError

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
    response = _get(session, f'{URL_BASE}/m/shop/view.php', params={'gs_id': gs_id})
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

def _submit_cart(session: requests.Session, act: str) -> Optional[requests.Response]:
    '''Submits all cart items with the action. Returns None if the cart is empty'''
    response = _get(session, f'{URL_BASE}/m/shop/cart.php')
    form = _get_form(response, 'form[name="frmcartlist"]')
    fields = [field for field in _form_fields(form) if not field[0].startswith('ct_chk[')]
    items = [str(c['name']) for c in form.select('input[name^="ct_chk["]')]
    if len(items) == 0:
        return None
    fields += [(item, '1') for item in items]
    _set_field(fields, 'act', act)
    return _post(session, urljoin(response.url, str(form.get('action', ''))), fields)

def _clear_cart(session: requests.Session) -> None:
    '''Removes all products from the cart. The account is shared by all
    purchase orders, so a failed order may leave its products there'''
    _submit_cart(session, 'alldelete')

def _place_order(session: requests.Session, purchase_order: PurchaseOrder,
                 receiver_name: str) -> dict[str, Any]:
    '''Orders products in the cart with virtual account payment.
    Returns vendor's order ID, payment account and total price'''
    response = _submit_cart(session, 'buy')
    if response is None:
        raise PurchaseOrderError(purchase_order, message="The cart is empty")
    form = _get_form(response, 'form[action*="orderformupdate"]')
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

    response = _post(session, urljoin(response.url, str(form.get('action', ''))), fields)
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
    response = _get(session, f'{URL_BASE}/m/shop/orderinquiry.php', params={
        'shop_table_name': 'shop_order',
        'fr_date': from_date.isoformat(),
        'to_date': to_date.isoformat()
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
