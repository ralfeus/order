from functools import reduce
from app.tools import get_document_from_url
from datetime import datetime, timedelta
import logging
import re
import subprocess
from urllib.parse import urlencode

from pytz import timezone

from app.exceptions import AtomyLoginError, HTTPError, PurchaseOrderError
from app.orders.models import Subcustomer
from app.orders.models.order_product import OrderProductStatus
from app.purchase.models import PurchaseOrder
from . import PurchaseOrderVendorBase

class AtomyCenter(PurchaseOrderVendorBase):
    __po_params = {}
    __purchase_order = None
    __session_cookies = []
    __username = 'atomy1026'
    __password = '5714'

    def __init__(self, browser=None, logger:logging.Logger=None, config=None):
        super().__init__()
        # self.__browser_attr = browser
        log_level = None
        if logger:
            log_level = logger.level
        else:
            if config:
                log_level = config['LOG_LEVEL']
            else:
                log_level = logging.INFO
        logging.basicConfig(level=log_level)
        logger = logging.getLogger('AtomyCenter')
        logger.setLevel(log_level)
        self.__original_logger = self.__logger = logger
        self.__logger.info(logging.getLevelName(self.__logger.getEffectiveLevel()))
        self.__config = config

    def __str__(self):
        return "Atomy - Center"

    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        '''Posts purchase order on AtomyCenter'''
        self.__logger = self.__original_logger.getChild(purchase_order.id)
        self.__purchase_order = purchase_order
        self.__session_cookies = self.login()
        self.__init_order_request()
        self.__set_customer_id(purchase_order.customer.username)
        self.__set_purchase_date(purchase_order.purchase_date)
        self.__set_phones(purchase_order.contact_phone)
        ordered_products = self.__add_products(purchase_order.order_products)
        self.__set_receiver_address(purchase_order.address)
        self.__set_shipment_options(ordered_products)
        self.__set_purchase_order_id(purchase_order.id[11:])
        self.__set_payment_method()
        self.__set_payment_destination(purchase_order.bank_id)
        self.__set_payment_mobile(purchase_order.payment_phone)
        self.__set_tax_info(purchase_order.company.tax_id)
        po_params = self.__submit_order()
        purchase_order.vendor_po_id = po_params[0]
        purchase_order.payment_account = po_params[1]
        self._set_order_products_status(ordered_products, OrderProductStatus.purchased)
        return purchase_order

    def __init_order_request(self):
        self.__po_params = {
            'deli_check': 3,
            'tag_sum':0,
            'card_amt': 0,
            'verify': 1,
            'bu_code': 1026,
            'deli_gubun': 3,
            'mile_amt': 0
        }

    def update_purchase_orders_status(self, customer: Subcustomer, customer_pos: list):
        from .atomy_quick import AtomyQuick
        self.__logger = self.__original_logger.getChild('update_purchase_orders_status')
        proxy = AtomyQuick(None, self.__logger, self.__config)
        proxy.update_purchase_orders_status(customer, customer_pos)
        del proxy

    def __get_product(self, product_id):
        result = get_document_from_url(
            url=f"https://atomy.kr/center/pop_mcode.asp?id={product_id}",
            encoding='euc-kr',
            headers=[{'Cookie': c} for c in self.__session_cookies ]
        )
        script = result.cssselect('script')[0].text
        return {
            'vat_price': int(re.search(r'vat_price\.value = "(\d+)"', script).groups()[0])
        } \
            if re.search(r'alert\(.+\);', result.text) is None \
            else None

    def __add_products(self, order_products):
        self.__logger.info("Adding products")
        ordered_products = []
        field_num = 1
        tot_amt = tot_pv = tot_qty = tot_vat = 0
        for op in order_products:
            if not op.product.purchase:
                self.__logger.warning("The product %s is exempted from purchase", op.product_id)
                continue
            if op.quantity <= 0:
                self.__logger.warning('The product %s has wrong quantity %s',
                    op.product_id, op.quantity)
                continue
            try:
                product_id = '0' * (6 - len(op.product_id)) + op.product_id
                product = self.__get_product(product_id)
                if product:
                    self.__po_params = {**self.__po_params,
                        f'mgubun{field_num}': 1,
                        f'vat_price{field_num}': product['vat_price'],
                        f'vat_amt{field_num}' : product['vat_price'] * op.quantity,
                        f'pv_price{field_num}': op.product.points,
                        f'pv_amt{field_num}': op.product.points * op.quantity,
                        f'sale_qty{field_num}': op.quantity,
                        f'sale_price{field_num}': op.price,
                        f'sale_amt{field_num}': (op.price - product['vat_price']) * op.quantity,
                        f'deli_amt{field_num}': op.price * op.quantity,
                        f'tot_amt{field_num}': op.price * op.quantity,
                        f'mdeli_gubun{field_num}': 0,
                        f'mquick_product{field_num}': 0,
                        f'material_code{field_num}': product_id,
                        f'limit_per_qty{field_num}': 0
                    }
                    tot_amt += op.price * op.quantity
                    tot_qty += op.quantity
                    tot_pv += op.product.points * op.quantity
                    tot_vat += product['vat_price']
                    ordered_products.append(op)
                    field_num += 1
                    self.__logger.info("Added product %s", op.product_id)
                else:
                    self.__logger.warning("The product %s is not available", product_id)
            except Exception:
                self.__logger.exception("Couldn't add product %s", op.product_id)
        self.__po_params['good_amt'] = tot_amt
        self.__po_params['ipgum_amt'] = tot_amt
        self.__po_params['tot_amt'] = tot_amt
        self.__po_params['tot_deli'] = tot_amt
        self.__po_params['tot_pv'] = tot_pv
        self.__po_params['tot_qty'] = tot_qty
        self.__po_params['tot_vat'] = tot_vat
        return ordered_products

    def __set_shipment_options(self, ordered_products):
        logger = self.__logger.getChild('__set_shipment_options')
        logger.debug('Set shipment options')
        free_shipping_eligible_amount = reduce(
            lambda acc, op: acc + (op.price * op.quantity)
                if not op.product.separate_shipping else 0,
            ordered_products, 0)
        local_shipment = free_shipping_eligible_amount < self.__config['FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD']
        if local_shipment:
            logger.debug("Setting combined shipment params")
            self.__po_params['tag_gubun'] = 1
            self.__po_params['cPackingMemo2'] = 'on'
        else:
            logger.debug('No combined shipment is needed')
            self.__po_params['tag_gubun'] = 0

    def __is_purchase_date_valid(self, purchase_date):
        tz = timezone('Asia/Seoul')
        today = datetime.now().astimezone(tz)
        min_date = (today - timedelta(days=2)).date()
        max_date = (today + timedelta(days=1)).date()
        return purchase_date is None or \
            (purchase_date >= min_date and purchase_date <= max_date)

    # def __open_order(self):
    #     self.__browser.get('https://atomy.kr/center/c_sale_ins.asp')

    def __set_customer_id(self, customer_id):
        self.__logger.debug("Setting customer ID")
        self.__po_params['cust_no'] = customer_id
        self.__po_params['ipgum_name'] = self.__purchase_order.customer.name

    def __set_payment_destination(self, bank_id='06'):
        self.__logger.debug("Setting payment receiver")
        self.__po_params['bank_gubun'] = 1
        self.__po_params['bank'] = bank_id

    def __set_payment_method(self):
        self.__logger.debug("Setting payment method")
        self.__po_params['settle_gubun'] = 2

    def __set_phones(self, phone='010-6275-2045'):
        self.__logger.debug("Setting receiver phone number")
        self.__po_params['orderhp'] = phone
        self.__po_params['revhp'] = phone

    def __set_payment_mobile(self, phone='010-6275-2045'):
        self.__logger.debug("Setting payment phone number")
        if not re.match(r'^\d{3}-\d{4}-\d{4}', phone):
            self.__logger.info("Payment phone isn't set as it isn't provided")
            return
        self.__po_params['virhp'] = phone

    def __set_purchase_date(self, purchase_date):
        self.__logger.debug("Setting sale date")
        if purchase_date and self.__is_purchase_date_valid(purchase_date):
            sale_date = purchase_date
        else:
            sale_date = datetime.now()
        if sale_date.weekday() == 6 or (sale_date.month, sale_date.day) == (1, 1):
            sale_date += timedelta(days=1)
        self.__po_params['sale_date'] = sale_date.strftime('%Y-%m-%d')

    def __set_purchase_order_id(self, purchase_order_id):
        self.__logger.debug("Setting purchase order ID")
        self.__po_params['revname'] = purchase_order_id.replace('-', 'ㅡ')

    def __set_receiver_address(self, address={
            'zip': '08584',
            'address_1': '서울특별시 금천구 두산로 70 (독산동)',
            'address_2': '291-1번지 현대지식산업센터  A동 605호'}):
        self.__logger.debug("Setting shipment address")
        self.__po_params['revzip'] = address['zip']
        self.__po_params['addr1'] = address['address_1']
        self.__po_params['addr2'] = address['address_2']

    def __set_tax_info(self, tax_id=(123, 34, 26780)):
        self.__logger.debug("Setting counteragent tax information")
        self.__logger.debu(tax_id)
        if tax_id == ('', '', ''): # No company
            self.__po_params = {**self.__po_params,
                'tax_check': 0,
                'tax_l_gubun': 0,
                'tax_m_gubun': 0
            }
        else:
            self.__po_params = {**self.__po_params,
                'tax_check': 1,
                'tax_l_gubun': 2,
                'tax_m_gubun': 3,
                'tax_b_num1': tax_id[0],
                'tax_b_num2': tax_id[1],
                'tax_b_num3': tax_id[2],
                'tax_l_num': '{}-{}-{}' % tax_id
            }

    def __submit_order(self):
        self.__logger.info("Submitting the order")
        result = self.__send_order_post_request()
        self.__logger.debug(result)
        return result
        
    def __send_order_post_request(self):
        self.__logger.debug(self.__po_params)
        try:
            post_order_doc = get_document_from_url(
                url='https://atomy.kr/center/payreq.asp',
                encoding='euc-kr',
                headers=[{'Cookie': c} for c in self.__session_cookies] + [
                    {'Referer': 'https://atomy.kr/center/c_sale_ins.asp'}
                ],
                raw_data=urlencode(self.__po_params, encoding='euc-kr')
            )
            script = post_order_doc.cssselect('head script')[0].text
            message_match = re.search(r"alert\(['\"](.*)['\"]\);", script)
            if message_match is not None:
                message = message_match.groups()[0]
                raise PurchaseOrderError(self.__purchase_order, self, message)
            return \
                post_order_doc.cssselect('#LGD_OID')[0].attrib['value'], \
                self.__get_bank_account_number(script)
        except HTTPError:
            self.__logger.warning(self.__po_params)
            raise PurchaseOrderError(self.__purchase_order, self, "Unexpected error has occurred")

    def __get_bank_account_number(self, content):
        match = re.search(r'LGD_ACCOUNTNUM[^"]+"(\d+)"', content)
        if match is not None:
            return match.groups()[0]
        return None

    def login(self, username='atomy1026', password='5714'):
        ''' Logins to Atomy customer section '''
        output = subprocess.run([
            '/usr/bin/curl',
            'https://www.atomy.kr/center/check_user.asp',
            '-H',
            'Referer: https://www.atomy.kr/center/login.asp?src=/center/c_sale_ins.asp',
            '--data-raw',
            f'src=&admin_id={username}&passwd={password}',
            '-v'
            ],
            encoding='euc-kr', stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=False)
        if re.search('< location: center_main', output.stderr):
            return re.findall('set-cookie: (.*)', output.stderr)
        raise AtomyLoginError(username)
