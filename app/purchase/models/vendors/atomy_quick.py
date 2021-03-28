''' Fills and submits purchase order at Atomy
using quick order'''
from functools import reduce
from app.tools import get_document_from_url
from datetime import datetime, timedelta
import json
import logging
from pytz import timezone
import re
from time import sleep
from selenium.common.exceptions import StaleElementReferenceException, \
    JavascriptException

from app.exceptions import AtomyLoginError, NoPurchaseOrderError, ProductNotAvailableError, PurchaseOrderError
from app.orders.models.order_product import OrderProductStatus
from app.utils.atomy import atomy_login
from app.utils.browser import Browser, Keys
from . import PurchaseOrderVendorBase

ERROR_FOREIGN_ACCOUNT = "Can't add product %s for customer %s as it's available in customer's country"
ERROR_OUT_OF_STOCK = '해당 상품코드의 상품은 품절로 주문이 불가능합니다'

class AtomyQuick(PurchaseOrderVendorBase):
    ''' Manages purchase order at Atomy via quick order '''
    __browser: Browser = None
    __is_browser_created_locally = False
    __logger: logging.Logger = None
    __purchase_order = None

    def __init__(self, browser=None, logger: logging.Logger=None, config=None):
        super().__init__()
        self.__browser_attr = browser
        log_level = None
        if logger:
            log_level = logger.level
        else:
            if config:
                log_level = config['LOG_LEVEL']
            else:
                log_level = logging.INFO
        logging.basicConfig(level=log_level)
        logger = logging.getLogger('AtomyQuick')
        logger.setLevel(log_level)
        self.__original_logger = self.__logger = logger
        self.__logger.info(logging.getLevelName(self.__logger.getEffectiveLevel()))
        self.__config = config
        self.__session_cookies = None
        self.__po_params = {}

    def __del__(self):
        if self.__is_browser_created_locally:
            try:
                self.__browser.quit()
            except:
                pass

    def __str__(self):
        return "Atomy - Quick order"

    @property
    def __browser(self):
        if self.__browser_attr is None:
            self.__browser_attr = Browser(config=self.__config)
            self.__is_browser_created_locally = True
        return self.__browser_attr

    def post_purchase_order(self, purchase_order):
        ''' Posts a purchase order to Atomy based on provided data '''
        self.__logger = self.__original_logger.getChild(purchase_order.id)
        # First check whether purchase date set is in acceptable bounds
        if not self.__is_purchase_date_valid(purchase_order.purchase_date):
            self.__logger.info("Skip <%s>: purchase date is %s",
                purchase_order.id, purchase_order.purchase_date)
            return purchase_order
        self.__purchase_order = purchase_order
        self.__logger.info("Logging in...")
        try:
            self.__session_cookies = atomy_login(
                purchase_order.customer.username,
                purchase_order.customer.password,
                run_browser=False)
            # return self.__send_order_post_request()
            self.__init_quick_order(purchase_order)
            ordered_products = self.__add_products(purchase_order.order_products)
            self.__set_purchase_date(purchase_order.purchase_date)
            self.__set_sender_name()
            self.__set_purchase_order_id(purchase_order.id[11:]) # Receiver name
            self.__set_local_shipment(purchase_order)
            self.__set_receiver_mobile(purchase_order.contact_phone)
            self.__set_receiver_address(purchase_order.address)
            self.__set_payment_method()
            self.__set_payment_mobile(purchase_order.payment_phone)
            self.__set_payment_destination(purchase_order.bank_id)
            self.__set_tax_info(purchase_order.company.tax_id)
            # self.__set_mobile_consent()
            po_params = self.__submit_order()
            purchase_order.vendor_po_id = po_params[0]
            purchase_order.payment_account = po_params[1]
            self._set_order_products_status(ordered_products, OrderProductStatus.purchased)
            return purchase_order
        except AtomyLoginError as ex:
            self.__logger.warning("Couldn't log on as a customer. %s", str(ex.args))
            raise ex
        except PurchaseOrderError as ex:
            self.__logger.warning(ex)
            if ex.retry:
                self.__logger.warning("Retrying %s", purchase_order.id)
                return self.post_purchase_order(purchase_order)
        except Exception as ex:
            # Saving page for investigation
            # with open(f'order_complete-{purchase_order.id}.html', 'w') as f:
            #     f.write(self.__browser.page_source)
            self.__logger.exception("Failed to post an order %s", purchase_order.id)
            raise ex

    @property
    def browser(self):
        return self.__browser

    def __init_quick_order(self, purchase_order):
        doc = get_document_from_url(
            url='https://www.atomy.kr/v2/Home/Payment/QuickOrder',
            encoding='utf-8',
            headers=[{'Cookie': c} for c in self.__session_cookies ]
        )
        self.__po_params = {**self.__po_params,
            'DeliCheck': 3,
            'IpgumName': purchase_order.customer.name,
            'OrderUrl': '%2Fv2%2FHome%2FPayment%2FQuickOrder%3F_%3D1616863579709',
            'PaymentType': 2,
            'PricePrint': 1,
            'TagGubun': 2
        }

    def __send_order_post_request(self):
        raw = '&'.join(["%s=%s" % p for p in self.__po_params.items()])
        post_order_doc = get_document_from_url(
            url='https://www.atomy.kr/v2/Home/Payment/PayReq_CrossPlatform2',
            encoding='utf-8',
            headers=[{'Cookie': c} for c in self.__session_cookies],
            # raw_data='CartList[0].CustPrice=12800&CartList[0].MaterialCode=000454&CartList[0].PvAmt=4700&CartList[0].PvPrice=4700&CartList[0].Qty=1&CartList[0].TotAmt=12800&Addr1=1111&Addr2=1111&BankGubun=1&CardGubun=0&DeliCheck=3&OrderHp=010-5635-2045&OrderUrl=%2Fv2%2FHome%2FPayment%2FQuickOrder%3F_%3D1616863579709&RevHp=010-5635-2045&TagGubun=2&RevName=111&Revzip=1111&SaleDate=2021-03-27&SendName=dumb&SettleGubun=2&TagSum=2500&TotAmt=12800&TotPv=4700&TotQty=1&PackingGubun=0&PricePrint=1&PaymentType=2&Bank=06&IpgumAmt=15300&IpgumName=Моє імя&TaxCheck=0&TaxLGubun=0&TaxLNum=&TaxMGubun=0&VirHp=010-5635-2045&CloseDate=2021-04-02'
            # raw_data='DeliCheck=3&IpgumName=Балыкбаева Гулжамал&OrderUrl=%2Fv2%2FHome%2FPayment%2FQuickOrder%3F_%3D1616863579709&PaymentType=2&PricePrint=1&TagGubun=2&CartList[0].CustPrice=34800&CartList[0].MaterialCode=004008&CartList[0].PvAmt=170000&CartList[0].PvPrice=17000&CartList[0].Qty=10&CartList[0].TotAmt=348000&TotAmt=348000&IpgumAmt=348000&TotPv=170000&TotQty=10&CloseDate=2021-03-31&SaleDate=2021-03-28&SendName=dumb&RevName=0001ㅡ001&PackingGubun=0&TagSum=0&OrderHp=010-5635-2045&RevHp=010-5635-2045&Addr1=서울특별시 금천구 두산로 70 (독산동)&Addr2=291-1번지 현대지식산업센터  A동 605호&Revzip=08584&CardGubun=0&BankGubun=1&SettleGubun=2&VirHp=010-5635-2045&Bank=06&TaxCheck=1&TaxLGubun=2&TaxMGubun=3&TaxLNum=111-11-11111',
            raw_data='&'.join(["%s=%s" % p for p in self.__po_params.items()])
        )
        self.__logger.info(post_order_doc.cssselect('head script')[1].text)
        return post_order_doc.cssselect('#LGD_OID')[0].attrib['value']

    def __get_order_details(self, order_id):
        order_details_doc = get_document_from_url(
            url='https://www.atomy.kr/v2/Home/MyAtomyMall/GetMyOrderView',
            encoding='utf-8',
            headers=[{'Cookie': c} for c in self.__session_cookies ] + [
                {'Content-Type': 'application/json'}
            ],
            raw_data='{"SaleNum":"%s","CustNo":"%s"}' % \
                (order_id, self.__purchase_order.customer.username)
        )
        return json.loads(order_details_doc.text)

    def __open_quick_order(self):
        self.__logger.debug(" Open quick order")
        self.__browser.get('https://www.atomy.kr/v2/Home/Product/MallMain')
        # quick_order = self.__browser.get_element_by_id('aQuickOrder2')
        # quick_order.click()
        self.__browser.execute_script("laypop('one', '1140', '640', '/v2/Home/Payment/QuickOrder', '빠른주문', 'scroll', '')")
        try:
            self.__browser.get_element_by_class('layPop')
        except:
            raise PurchaseOrderError(self.__purchase_order, self, "Couldn't open quick order")
        # self.__browser.save_screenshot(realpath('01-quick-order.png'))

    def __set_product_code(self, input, value):
        input.send_keys(Keys.RETURN)
        sleep(.5)
        alert = self.__browser.get_alert()
        if input.get_attribute('value') == value:
            self.__logger.debug('The value is not entered so far')
            if alert:
                if ERROR_OUT_OF_STOCK in alert:
                    raise ProductNotAvailableError(value, final=True)
                raise PurchaseOrderError(
                    self.__purchase_order, self,
                    "Couldn't enter %s product code: %s" % (value, alert), retry=True)

    def __set_product_quantity(self, input, value):
        input.clear()
        input.send_keys(value)
        if int(input.get_attribute('value')) != value:
            self.__logger.debug('The quantity value is not entered so far')
            raise PurchaseOrderError(
                self.__purchase_order, self,
                "Couldn't enter %s product quantity" % value, retry=True)

    def __add_products(self, order_products):
        self.__logger.debug("Adding products")
        ordered_products = []
        tot_amt = tot_pv = tot_qty = 0
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
                if self.__is_product_valid(product_id):
                    index = len(ordered_products)
                    self.__po_params[f'CartList[{index}].CustPrice'] = op.price
                    self.__po_params[f'CartList[{index}].MaterialCode'] = product_id
                    self.__po_params[f'CartList[{index}].PvAmt'] = op.product.points * op.quantity
                    self.__po_params[f'CartList[{index}].PvPrice'] = op.product.points
                    self.__po_params[f'CartList[{index}].Qty'] = op.quantity
                    self.__po_params[f'CartList[{index}].TotAmt'] = op.price * op.quantity
                    tot_amt += op.price * op.quantity
                    tot_pv += op.product.points * op.quantity
                    tot_qty += op.quantity
                    ordered_products.append(op)
                    self.__logger.debug(f"Added product {op.product_id}")
                else:
                    raise ProductNotAvailableError(product_id)
            except ProductNotAvailableError:
                self.__logger.warning("Product %s is not available", op.product_id)
            except PurchaseOrderError as ex:
                raise ex
            except Exception:
                self.__logger.exception("Couldn't add product %s", op.product_id)
        # self.__browser.save_screenshot(realpath('02-products.png'))
        self.__po_params['TotAmt'] = self.__po_params['IpgumAmt'] = tot_amt
        self.__po_params['TotPv'] = tot_pv
        self.__po_params['TotQty'] = tot_qty
        return ordered_products

    def __is_product_valid(self, product_id):
        result = get_document_from_url(
            url="https://www.atomy.kr/v2/Home/Payment/GetMCode",
            encoding='utf-8',
            headers=[{'Cookie': c} for c in self.__session_cookies ] + [
                {'Content-Type': 'application/json'}
            ],
            raw_data='{"MaterialCode":"%s"}' % product_id
        )
        result = json.loads(result.text)
        return result['jsonData'] is not None

    def __is_purchase_date_valid(self, purchase_date):
        tz = timezone('Asia/Seoul')
        today = datetime.now().astimezone(tz)
        min_date = (today - timedelta(days=2)).date()
        max_date = (today + timedelta(days=1)).date()
        return purchase_date is None or \
            (purchase_date >= min_date and purchase_date <= max_date)
                
    def __set_purchase_date(self, purchase_date):
        if purchase_date and self.__is_purchase_date_valid(purchase_date):
            sale_date = purchase_date
        else:
            sale_date = datetime.now()
        self.__po_params['CloseDate'] = (sale_date + timedelta(days=3)).strftime('%Y-%m-%d')
        self.__po_params['SaleDate'] = sale_date.strftime('%Y-%m-%d')

    def __set_local_shipment(self, purchase_order):
        free_shipping_eligible_amount = reduce(
            lambda acc, op: acc + (op.price * op.quantity)
                if not op.product.separate_shipping else 0,
            purchase_order.order_products, 0)
        local_shipment = free_shipping_eligible_amount < self.__config['FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD']
        if local_shipment:
            self.__logger.debug("Setting local shipment params")
            self.__po_params['PackingGubun'] = 1
            self.__po_params['PackingMemo'] = purchase_order.contact_phone + \
                '/' + purchase_order.address.zip
            self.__po_params['TagSum'] = self.__config['LOCAL_SHIPPING_COST']
            self.__po_params['IpgumAmt'] += self.__config['LOCAL_SHIPPING_COST']
        else:
            self.__po_params['PackingGubun'] = 0
            self.__po_params['TagSum'] = 0

    def __set_mobile_consent(self):
        self.__logger.debug("Setting mobile consent")
        self.__browser.click_by_id('chkAgree_tax_gubun2')

    def __set_sender_name(self):
        self.__logger.debug("Setting sender name")
        self.__po_params['SendName'] = 'dumb'

    def __set_purchase_order_id(self, purchase_order_id):
        self.__logger.debug("Setting purchase order ID")
        adapted_po_id = purchase_order_id.replace('-', 'ㅡ')
        self.__po_params['RevName'] = adapted_po_id

    def __set_receiver_mobile(self, phone='010-6275-2045'):
        self.__logger.debug("Setting receiver phone number")
        self.__po_params['OrderHp'] = phone
        self.__po_params['RevHp'] = phone

    def __set_payment_mobile(self, phone='010-6275-2045'):
        self.__logger.debug("Setting phone number for payment notification")
        if phone != '':
            self.__po_params['VirHp'] = phone
        else:
            self.__logger.info('Payment phone isn\'t provided')

    def __set_receiver_address(self, address={
            'zip': '08584',
            'address_1': '서울특별시 금천구 두산로 70 (독산동)',
            'address_2': '291-1번지 현대지식산업센터  A동 605호'}):
        self.__logger.debug("Setting shipment address")
        self.__po_params['Addr1'] = address['address_1']
        self.__po_params['Addr2'] = address['address_2']
        self.__po_params['Revzip'] = address['zip']

    def __set_payment_method(self):
        self.__logger.debug("Setting payment method")
        self.__po_params['CardGubun'] = 0
        self.__po_params['BankGubun'] = 1
        self.__po_params['SettleGubun'] = 2

    def __set_payment_destination(self, bank_id='06'):
        self.__logger.debug("Setting payment receiver")
        self.__po_params['Bank'] = bank_id

    def __set_tax_info(self, tax_id=(123, 34, 26780)):
        self.__logger.debug("Setting counteragent tax information")
        if tax_id != ('', '', ''): # Company is set
            self.__po_params['TaxCheck'] = 1
            self.__po_params['TaxLGubun'] = 2
            self.__po_params['TaxMGubun'] = 3
            self.__po_params['TaxLNum'] = "%s-%s-%s" % tax_id
        else:
            self.__po_params['TaxCheck'] = 0
            self.__po_params['TaxLGubun'] = 0
            self.__po_params['TaxMGubun'] = 0

    def __submit_order(self):
        self.__logger.info("Submitting the order")
        try:
            order_id = self.__send_order_post_request()
            vendor_po = self.__get_order_details(order_id=order_id)
            return order_id, vendor_po['jsonData'][0]['IpgumAccountNo']
        except Exception as ex:
            self.__logger.debug("Couldn't get order completion page")
            raise Exception(ex)
        
    def update_purchase_order_status(self, purchase_order):
        self.__logger.info("%s: Logging in...", __name__)
        atomy_login(
            purchase_order.customer.username,
            purchase_order.customer.password,
            self.__browser)
        self.__logger.debug("%s: Getting POs from Atomy...", __name__)
        vendor_purchase_orders = self.__get_purchase_orders()
        self.__logger.info("%s: Got %s POs", __name__, len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            print(str(o))
            if o['id'] == purchase_order.vendor_po_id:
                purchase_order.status = o['status']
                return purchase_order

        raise NoPurchaseOrderError(
            'No corresponding purchase order for Atomy PO <%s> was found' %
            o['id'])
        

    def update_purchase_orders_status(self, subcustomer, purchase_orders):
        self.__logger.info('Attempting to log in as %s...', subcustomer.name)
        atomy_login(
            subcustomer.username,
            subcustomer.password,
            self.__browser)
        self.__logger.info('Getting subcustomer\'s POs')
        vendor_purchase_orders = self.__get_purchase_orders()
        self.__logger.debug('Got %s POs', len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            self.__logger.info(str(o))
            filtered_po = filter(
                lambda po: po and po.vendor_po_id == o['id'],
                purchase_orders)
            try:
                po = next(filtered_po)
                po.status = o['status']
            except StopIteration:
                self.__logger.warning(
                    'No corresponding purchase order for Atomy PO <%s> was found', 
                    o['id'])

    def __get_purchase_orders(self):
        # self.__logger.info("Getting orders")
        self.__browser.get("https://www.atomy.kr/v2/Home/MyAtomyMall/OrderList")
        try:
            self.__browser.execute_script('SetDateSearch("d", -7)')
        except JavascriptException:
            pass # If we can't set week range let's work with what we have
        order_lines = []
        while not len(order_lines):
            # self.__logger.info('Getting order lines')
            sleep(1)
            order_lines = self.__browser.find_elements_by_css_selector(
                "tbody#tbdList tr:nth-child(odd)")
            try:
                if len(order_lines) and order_lines[0].text == '조회된 정보가 없습니다.':
                    order_lines = []
                break
            except StaleElementReferenceException:
                self.__logger.warn("Couldn't get order line text. Retrying...")
                order_lines = []
        orders = list(map(self.__line_to_dict,
            order_lines
        ))
        return orders

    def __line_to_dict(self, l):
        from app.purchase.models import PurchaseOrderStatus
        po_statuses = {
            '주문접수': PurchaseOrderStatus.posted,
            '배송중': PurchaseOrderStatus.shipped,
            '미결제마감': PurchaseOrderStatus.payment_past_due,
            '결제완료': PurchaseOrderStatus.paid,
            '상품준비중': PurchaseOrderStatus.paid,
            '주문취소': PurchaseOrderStatus.cancelled,
            '매출취소': PurchaseOrderStatus.cancelled,
            '배송완료': PurchaseOrderStatus.delivered,
            '반품': PurchaseOrderStatus.delivered
        }       
        # print(l.text)
        acc_num_text = l.find_element_by_css_selector('td:nth-child(2)').text
        status_text = l.find_element_by_css_selector('p.fs18').text
        return {
            'id': re.search('^\d+', acc_num_text)[0],
            'status': po_statuses[status_text]
        }
