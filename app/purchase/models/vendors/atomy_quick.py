''' Fills and submits purchase order at Atomy
using quick order'''
from functools import reduce
from app.tools import get_document_from_url
from datetime import datetime, timedelta
import json
import logging
from pytz import timezone
import re

from app.exceptions import AtomyLoginError, HTTPError, NoPurchaseOrderError, ProductNotAvailableError, PurchaseOrderError
from app.orders.models.order_product import OrderProductStatus
from app.utils.atomy import atomy_login
from . import PurchaseOrderVendorBase

ERROR_FOREIGN_ACCOUNT = "Can't add product %s for customer %s as it's available in customer's country"
ERROR_OUT_OF_STOCK = '해당 상품코드의 상품은 품절로 주문이 불가능합니다'

class AtomyQuick(PurchaseOrderVendorBase):
    ''' Manages purchase order at Atomy via quick order '''
    __logger: logging.Logger = None
    __purchase_order = None

    def __init__(self, browser=None, logger: logging.Logger=None, config=None):
        super().__init__()
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

    def __str__(self):
        return "Atomy - Quick order"

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
        # raw = '&'.join(["%s=%s" % p for p in self.__po_params.items()])
        self.__po_params['TotAmt'] = 0
        try:
            post_order_doc = get_document_from_url(
                url='https://www.atomy.kr/v2/Home/Payment/PayReq_CrossPlatform2',
                encoding='utf-8',
                headers=[{'Cookie': c} for c in self.__session_cookies],
                raw_data='&'.join(["%s=%s" % p for p in self.__po_params.items()])
            )
            return post_order_doc.cssselect('#LGD_OID')[0].attrib['value']
        except KeyError: # Couldn't get order ID
            script = post_order_doc.cssselect('head script')[1].text
            message_match = re.search("var responseMsg = '(.*)';", script)
            if message_match is not None:
                message = message_match.groups()[0]
                raise PurchaseOrderError(self.__purchase_order, self, message)
        except HTTPError:
            raise PurchaseOrderError(self.__purchase_order, self, "Unexpected error has occurred")

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
        logger = self.__logger.getChild('update_purchase_order_status')
        logger.info('Updating %s status', purchase_order.id)
        logger.info("Logging in...")
        self.__session_cookies = atomy_login(
            purchase_order.customer.username,
            purchase_order.customer.password,
            run_browser=False)
        logger.debug("Getting POs from Atomy...")
        vendor_purchase_orders = self.__get_purchase_orders()
        self.__logger.info("Got %s POs", len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            logger.debug(str(o))
            if o['id'] == purchase_order.vendor_po_id:
                purchase_order.status = o['status']
                return purchase_order

        raise NoPurchaseOrderError(
            'No corresponding purchase order for Atomy PO <%s> was found' %
            o['id'])
        

    def update_purchase_orders_status(self, subcustomer, purchase_orders):
        logger = self.__logger.getChild('update_purchase_orders_status')
        logger.info('Updating %s POs status', len(purchase_orders))
        self.__logger.info('Attempting to log in as %s...', subcustomer.name)
        self.__session_cookies = atomy_login(
            subcustomer.username,
            subcustomer.password,
            run_browser=False)
        logger.info('Getting subcustomer\'s POs')
        vendor_purchase_orders = self.__get_purchase_orders()
        logger.debug('Got %s POs', len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            logger.info(str(o))
            filtered_po = [po for po in purchase_orders 
                              if po and po.vendor_po_id == o['id']]
            try:
                filtered_po[0].status = o['status']
            except IndexError:
                logger.warning(
                    'No corresponding purchase order for Atomy PO <%s> was found', 
                    o['id'])

    def __get_purchase_orders(self):
        logger = self.__logger.getChild('__get_purchase_orders')
        logger.info('Getting purchase order')
        search_params = {
            "CurrentPage": 1,
            "PageSize": 100,
            "SDate": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            "EDate": (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
            "OrderStatus":""
        }
        response = get_document_from_url(
            url='https://www.atomy.kr/v2/Home/MyAtomyMall/GetMyOrderList',
            encoding='utf-8',
            headers=[{'Cookie': c} for c in self.__session_cookies ] + [
                {'Content-Type': 'application/json'}
            ],
            raw_data=json.dumps(search_params)
        )

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
        
        orders = [{
            'id': o['SaleNum'],
            'status': po_statuses[o['OrderStatusName']]
            } for o in json.loads(response.text)['jsonData']]

        return orders
