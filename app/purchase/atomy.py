''' Fills and submits purchase order at Atomy '''
from datetime import datetime, timedelta
from functools import reduce
from logging import Logger
from pytz import timezone
import re
from time import sleep
from selenium.common.exceptions import UnexpectedAlertPresentException,\
    StaleElementReferenceException

from app.exceptions import NoPurchaseOrderError
from app.utils.atomy import atomy_login
from app.utils.browser import Browser, Keys

ATTEMPTS_TOTAL = 3
ERROR_FOREIGN_ACCOUNT = "Can't add product %s for customer %s as it's available in customer's country"

class PurchaseOrderManager:
    ''' Fills and submits purchase order at Atomy '''
    __browser: Browser = None
    __logger: Logger = None

    def __init__(self, browser=None, logger=None, config=None):
        # if logger:
        #     logger.info(config)
        if browser is None:
            browser = Browser(
                executable_path=config['SELENIUM_DRIVER'] \
                    if config and config.get('SELENIUM_DRIVER') \
                    else None,
                connect_to=config['SELENIUM_BROWSER'] \
                    if config and config.get('SELENIUM_BROWSER') \
                    else None)
        self.__browser = browser
        self.__logger = logger

    def __del__(self):
        try:
            self.__browser.quit()
        except:
            pass

    def __log(self, entry):
        if self.__logger:
            self.__logger.info(entry)

    def post_purchase_order(self, purchase_order):
        ''' Posts a purchase order to Atomy based on provided data '''
        self.__log("PO: Logging in...")
        try:
            atomy_login(
                purchase_order.customer.username,
                purchase_order.customer.password,
                self.__browser)
            self.__open_quick_order()
            ordered_products = self.__add_products(purchase_order.order_products)
            self.__set_purchase_date(purchase_order.purchase_date)
            self.__set_sender_name()
            self.__set_purchase_order_id(purchase_order.id[11:]) # Receiver name
            self.__set_combined_shipment()
            self.__set_receiver_mobile(purchase_order.contact_phone)
            self.__set_receiver_address(purchase_order.address)
            self.__set_payment_method()
            self.__set_payment_mobile(purchase_order.payment_phone)
            self.__set_payment_destination(purchase_order.bank_id)
            self.__set_tax_info(purchase_order.company.tax_id)
            po_params = self.__submit_order()
            purchase_order.vendor_po_id = po_params[0]
            purchase_order.payment_account = po_params[1]
            for op in ordered_products:
                op.status = 'Purchased'
                op.when_changed = datetime.now()
            return purchase_order
        except Exception as ex:
            # Saving page for investigation
            # with open(f'order_complete-{purchase_order.id}.html', 'w') as f:
            #     f.write(self.__browser.page_source)
            self.__logger.exception("PO: Failed to post an order %s", purchase_order.id)
            raise ex

    @property
    def browser(self):
        return self.__browser

    def __open_quick_order(self):
        self.__log("PO: Open quick order")
        self.__browser.get('https://www.atomy.kr/v2/Home/Product/MallMain')
        quick_order = self.__browser.get_element_by_id('aQuickOrder2')
        quick_order.click()
        # self.__browser.save_screenshot(realpath('01-quick-order.png'))

    def __add_products(self, order_products):
        self.__log("PO: Adding products")
        # add_button = self.__browser.get_element_by_id('btnProductListSearch')
        product_code_input = self.__browser.get_element_by_class('selectGubunInput')
        ordered_products = []
        for op in order_products:
            if not op.product.purchase:
                self.__logger.warn("The product %s is exempted from purchase", op.product_id)
                continue
            if op.quantity <= 0:
                self.__logger.warning('The product %s has wrong quantity %s',
                    op.product_id, op.quantity)
                continue
            try:
                product_code_input.send_keys(op.product_id)
                while product_code_input.get_attribute('value') == op.product_id:
                    sleep(0.5)
                    product_code_input.send_keys(Keys.RETURN)
                    sleep(1)
                
                product_line = self.__browser.find_element_by_xpath(
                    '//tr[td[span[@class="materialCode"]]][last()]')
                quantity_input = product_line.find_element_by_xpath(
                    './/input[@class="numberic"]')
                quantity_input.clear()
                quantity_input.send_keys(op.quantity)
                
                ordered_products.append(op)
                self.__log(f"Added product {op.product_id}")
            except Exception as ex:
                product_code_input.clear()
                self.__logger.warning("Couldn't add product %s", op.product_id)
                self.__logger.warning(ex)
        # self.__browser.save_screenshot(realpath('02-products.png'))
        return ordered_products

    def __set_purchase_date(self, purchase_date):
        self.__log("PO: Setting purchase date")
        tz = timezone('Asia/Seoul')
        today = datetime.now().astimezone(tz)
        min_date = (today - timedelta(days=2)).date()
        max_date = (today + timedelta(days=1)).date()
        if purchase_date:
            purchase_date = purchase_date.date()
            if purchase_date >= min_date and \
                purchase_date <= max_date:
                date_str = purchase_date.strftime('%Y-%m-%d')
                self.__browser.execute_script(
                    f"document.getElementById('sSaleDate').value = '{date_str}'")
        # self.__browser.save_screenshot(realpath('03-purchase-date.png'))

    def __set_combined_shipment(self):
        local_shipment_node = self.__browser.find_element_by_css_selector(
            'ul#areaSummary li.pOr2 div em')
        if local_shipment_node.text == '2,500':
            self.__log("PO: Setting combined shipment")
            self.__browser.get_element_by_id('cPackingMemo2').click()
            self.__browser.get_element_by_id('all-agree').click()
            self.__browser.get_element_by_class('btnInsert').click()

    def __set_sender_name(self):
        self.__log("PO: Setting sender name")
        self.__browser.get_element_by_id('tSendName').send_keys('dumb')
        # self.__browser.save_screenshot(realpath('04-sender-name.png'))

    def __set_purchase_order_id(self, purchase_order_id):
        self.__log("PO: Setting purchase order ID")
        adapted_po_id = purchase_order_id.replace('-', 'ㅡ')
        self.__browser.get_element_by_id('tRevUserName').send_keys(adapted_po_id)
        # self.__browser.save_screenshot(realpath('05-po-id.png'))

    def __set_receiver_mobile(self, phone='010-6275-2045'):
        self.__log("PO: Setting receiver phone number")
        phone = phone.split('-')
        self.__browser.execute_script(
            f"document.getElementById('tRevCellPhone1').value = '{phone[0]}'")
        # self.__browser.get_element_by_id('tRevCellPhone1').send_keys(phone[0])
        self.__browser.get_element_by_id('tRevCellPhone2').send_keys(phone[1])
        self.__browser.get_element_by_id('tRevCellPhone3').send_keys(phone[2])
        # self.__browser.save_screenshot(realpath('06-rcv-mobile.png'))

    def __set_payment_mobile(self, phone='010-6275-2045'):
        self.__log("PO: Setting phone number for payment notification")
        phone = phone.split('-')
        self.__browser.execute_script(
            f"document.getElementById('tVirCellPhone1').value = '{phone[0]}'")
        # self.__browser.get_element_by_id('tVirCellPhone1').send_keys(phone[0])
        self.__browser.get_element_by_id('tVirCellPhone2').send_keys(phone[1])
        self.__browser.get_element_by_id('tVirCellPhone3').send_keys(phone[2])
        # self.__browser.save_screenshot(realpath('07-payment-mobile.png'))

    def __set_receiver_address(self, address={
            'zip': '08584',
            'address_1': '서울특별시 금천구 두산로 70 (독산동)',
            'address_2': '291-1번지 현대지식산업센터  A동 605호'}):
        self.__log("PO: Setting shipment address")
        self.__browser.execute_script(
            f"document.getElementById('tRevPostNo').value = \"{address['zip']}\"")
        # self.__browser.get_element_by_id('tRevPostNo').send_keys(address['zip'])
        self.__browser.execute_script(
            f"document.getElementById('tRevAddr1').value = \"{address['address_1']}\"")
        # self.__browser.get_element_by_id('tRevAddr1').send_keys(address['address_1'])
        self.__browser.get_element_by_id('tRevAddr2').send_keys(address['address_2'])
        # self.__browser.save_screenshot(realpath('08-rcv-address.png'))

    def __set_payment_method(self):
        self.__log("PO: Setting payment method")
        self.__browser.get_element_by_id('settleGubun2_input').click()
        # self.__browser.save_screenshot(realpath('09-payment-method.png'))

    def __set_payment_destination(self, bank_id='06'):
        self.__log("PO: Setting payment receiver")
        self.__browser.execute_script(
            f"document.getElementById('sBank').value = '{bank_id}'")
        # self.__browser.save_screenshot(realpath('10-payment-dst.png'))

    def __set_tax_info(self, tax_id=(123, 34, 26780)):
        self.__log("PO: Setting counteragent tax information")
        self.__browser.get_element_by_id('tax_gubun2').click()
        # self.__browser.execute_script(
        #     "document.getElementById('tTaxGubun1').value = '2'")
        tTaxGubun1 = self.__browser.get_element_by_id('tTaxGubun1')
        tTaxGubun1.click()
        tTaxGubun1.send_keys(Keys.DOWN)
        tTaxGubun1.send_keys(Keys.RETURN)
        self.__browser.get_element_by_id('tTaxBizNo1').send_keys(tax_id[0])
        self.__browser.get_element_by_id('tTaxBizNo2').send_keys(tax_id[1])
        self.__browser.get_element_by_id('tTaxBizNo3').send_keys(tax_id[2])
        # self.__browser.save_screenshot(realpath('11-tax-info.png'))

    def __submit_order(self):
        self.__log("PO: Submitting the order")
        self.__browser.get_element_by_id('chkAgree').click()
        # self.__browser.get_element_by_id('chkEduAgree').click()
        self.__browser.get_element_by_id('bPayment').click()
        try:
            self.__log('Waiting for order completion page')
            self.__browser.wait_for_url('https://www.atomy.kr/v2/Home/Payment/OrderComplete')
        except Exception as ex:
            self.__log("Couldn't get order completion page")
            raise Exception(ex)
            

        self.__logger.info("Order completion page is loaded.")
        return self.__get_po_params()
        

    def __get_po_params(self):
        self.__logger.info('Looking for purchase order number')
        po_id = None
        for attempt in range(1, 4):
            po_id_span = self.__browser.find_element_by_css_selector('div.cartTopbtn span.blue')
            if po_id_span:
                po_id = po_id_span.text
                break
        if not po_id:
            raise Exception("Couldn't get PO number")

        self.__logger.info('Looking for account number to pay')
        for attempt in range(1, 4): # Let's try to get account number several times
            headers = self.__browser.find_elements_by_xpath("//*[text()='입금계좌']")
            self.__logger.info("Got theaders")
            for header in headers:
                # next sibling contains account number
                if header.find_element_by_xpath('following-sibling::*').text:
                    self.__logger.info("Found bank account line")
                    bank_account = header.find_element_by_xpath('following-sibling::*')
                    return po_id, bank_account.text
            self.__logger.warning("Couldn't find account number at attempt %d.", attempt)
            sleep(5)
        self.__logger.warning("Gave up trying")  
        raise Exception("Couldn't find account number to pay to")

    def update_purchase_order_status(self, purchase_order):
        self.__logger.info("%s: Logging in...", __name__)
        atomy_login(
            purchase_order.customer.username,
            purchase_order.customer.password,
            self.__browser)
        self.__logger.info("%s: Getting POs from Atomy...", __name__)
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
        self.__browser.execute_script('SetDateSearch("m", -12)')
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
            '배송완료': PurchaseOrderStatus.delivered
        }       
        # print(l.text)
        acc_num_text = l.find_element_by_css_selector('td:nth-child(2)').text
        status_text = l.find_element_by_css_selector('p.fs18').text
        return {
            'id': re.search('^\d+', acc_num_text)[0],
            'status': po_statuses[status_text]
        }
