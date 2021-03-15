from datetime import datetime, timedelta
import logging
import re
from time import sleep

from pytz import timezone

from app.exceptions import AtomyLoginError
from app.orders.models import Subcustomer
from app.orders.models.order_product import OrderProductStatus
from app.purchase.models import PurchaseOrder
from app.utils.browser import Browser, Keys
from . import PurchaseOrderVendorBase

ERROR_OUT_OF_STOCK = '품절상품입니다'
WARNING_SEPARATE_SHIPPING = '무료배송(합포불가 개별발송) 상품입니다'

class AtomyCenter(PurchaseOrderVendorBase):
    __is_browser_created_locally = False

    def __init__(self, browser=None, logger:logging.Logger=None, config=None):
        super().__init__()
        self.__browser_attr = browser
        if logger:
            logging.basicConfig(level=logger.level)
        else:
            logging.basicConfig(level=logging.INFO)
        self.__original_logger = logging.getLogger('AtomyCenter')
        self.__config = config
        self.__username = 'atomy1026'
        self.__password = '5714'

    def __str__(self):
        return "Atomy - Center"

    @property
    def __browser(self):
        if self.__browser_attr is None:
            self.__browser_attr = Browser(config=self.__config)
            self.__is_browser_created_locally = True
        return self.__browser_attr

    def __del__(self):
        if self.__is_browser_created_locally:
            try:
                self.__browser_attr.quit()
            except:
                pass

    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        '''Posts purchase order on AtomyCenter'''
        self.__logger = self.__original_logger.getChild(purchase_order.id)
        self.login()
        self.__open_order()
        self.__set_customer_id(purchase_order.customer.username)
        self.__set_purchase_date(purchase_order.purchase_date)
        self.__set_phones(purchase_order.contact_phone)
        ordered_products = self.__add_products(purchase_order.order_products)
        self.__set_receiver_address(purchase_order.address)
        self.__set_combined_shipment()
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

    def update_purchase_orders_status(self, customer: Subcustomer, customer_pos: list):
        from .atomy_quick import AtomyQuick
        proxy = AtomyQuick(self.__browser, self.__logger, self.__config)
        proxy.update_purchase_orders_status(customer, customer_pos)
        del proxy

    def login(self):
        self.__logger.debug("Logging in")
        self.__browser.get('https://atomy.kr/center/login.asp')
        self.__browser.get_element_by_css('input[name="admin_id"]').send_keys(self.__username)
        password_input = self.__browser.get_element_by_css('input[name="passwd"]')
        password_input.send_keys(self.__password)
        password_input.send_keys(Keys.RETURN)
        try:
            self.__browser.wait_for_url('https://atomy.kr/center/center_main.asp')
        except Exception as ex:
            raise AtomyLoginError(ex)

    # def __set_product_quantity(self):
    #     while product_qty_input.get_attribute('value') != str(op.quantity):
    #         attempts_left -= 1
    #         self.__logger.debug("Qty field value is %s whilst must be %s",
    #             product_qty_input.get_attribute('value'), op.quantity)
    #         self.__logger.debug("%s attemts left", attempts_left)
    #         if not attempts_left:
    #             raise Exception("Couldn't set product quantity")
    #         self.__logger.debug("Clicking sale_qty%s field...", field_num)
    #         self.__browser.doubleclick(product_qty_input)
    #         self.__logger.debug("Typing %s to sale_qty%s...", op.quantity, field_num)
    #         product_qty_input.send_keys(op.quantity, Keys.TAB)
    #         sleep(0.3)
    #         self.__logger.debug("Now sale_qty%s is %s",
    #             field_num, product_qty_input.get_attribute('value'))

    def __add_products(self, order_products):
        self.__logger.info("Adding products")
        self.__browser.execute_script("$('img[src$=\"btn_D_add.gif\"]').click()")
        ordered_products = []
        field_num = 1
        for op in order_products:
            if not op.product.purchase:
                self.__logger.warning("The product %s is exempted from purchase", op.product_id)
                continue
            if op.quantity <= 0:
                self.__logger.warning('The product %s has wrong quantity %s',
                    op.product_id, op.quantity)
                continue
            try:
                self.__logger.debug("Getting input field material_code%s...", field_num)
                product_code_input = self.__browser.get_element_by_id(
                    f'material_code{field_num}')
                self.__logger.debug("\t...done")
                self.__logger.debug("Entering product code %s...", op.product_id)
                product_code_input.send_keys(op.product_id, Keys.TAB)
                sleep(.4)
                alert = self.__browser.get_alert()
                if alert:
                    if WARNING_SEPARATE_SHIPPING in alert:
                        self.__logger.info(alert)
                    elif ERROR_OUT_OF_STOCK in alert:
                        self.__logger.info( "Product %s is out of stock", op.product_id)
                        product_code_input.clear()
                        continue
                    else:
                        self.__logger.warning(alert)
                self.__logger.debug("\t...done")
                self.__logger.debug("Entering product %s quantity %s...", op.product_id, op.quantity)
                self.__logger.debug("Getting input field sale_qty%s...", field_num)
                product_qty_input = self.__browser.get_element_by_id(f'sale_qty{field_num}')
                self.__logger.debug("\t...done")
                attempts_left = 3
                while product_qty_input.get_attribute('value') != str(op.quantity):
                    attempts_left -= 1
                    self.__logger.debug("Qty field value is %s whilst must be %s",
                        product_qty_input.get_attribute('value'), op.quantity)
                    self.__logger.debug("%s attemts left", attempts_left)
                    if not attempts_left:
                        raise Exception("Couldn't set product quantity")
                    self.__logger.debug("Clicking sale_qty%s field...", field_num)
                    self.__browser.doubleclick(product_qty_input)
                    self.__logger.debug("Typing %s to sale_qty%s...", op.quantity, field_num)
                    product_qty_input.send_keys(op.quantity, Keys.TAB)
                    sleep(0.3)
                    self.__logger.debug("Now sale_qty%s is %s",
                        field_num, product_qty_input.get_attribute('value'))
                
                self.__logger.debug("Waiting tot_amt%s to update...", field_num)
                while not self.__browser.get_element_by_name(f'tot_amt{field_num}').get_attribute('value'):
                    sleep(0.3)
                    self.__logger.debug("\t...not yet")
                self.__logger.debug("Now tot_amt%s is %s", field_num, 
                    self.__browser.get_element_by_name(f'tot_amt{field_num}')
                        .get_attribute('value'))
                
                ordered_products.append(op)
                field_num += 1
                self.__logger.info("Added product %s", op.product_id)
            except Exception:
                product_code_input.clear()
                self.__logger.exception("Couldn't add product %s", op.product_id)
        return ordered_products

    def __set_combined_shipment(self):
        local_shipment_node = self.__browser.get_element_by_css('span#stot_sum')
        if int(re.sub('\\D', '', local_shipment_node.text)) < 30000:
            self.__logger.info("Setting combined shipment")
            combined_shipment_input = self.__browser.get_element_by_id('cPackingMemo2')
            self.__browser.execute_script("arguments[0].click();", combined_shipment_input)
            self.__browser.dismiss_alert()

    def __is_purchase_date_valid(self, purchase_date):
        tz = timezone('Asia/Seoul')
        today = datetime.now().astimezone(tz)
        min_date = (today - timedelta(days=2)).date()
        max_date = (today + timedelta(days=1)).date()
        return purchase_date is None or \
            (purchase_date >= min_date and purchase_date <= max_date)

    def __open_order(self):
        self.__browser.get('https://atomy.kr/center/c_sale_ins.asp')

    def __set_customer_id(self, customer_id):
        self.__logger.debug("Setting customer ID")
        cust_no_input = self.__browser.get_element_by_id('cust_no')
        cust_no_input.send_keys(customer_id)
        cust_no_input.send_keys(Keys.RETURN)

    def __set_payment_destination(self, bank_id='06'):
        self.__logger.debug("Setting payment receiver")
        self.__browser.execute_script(
            f"document.getElementsByName('bank')[0].value = '{bank_id}'")
        self.__browser.execute_script("check_ipgum_amt();")

    def __set_payment_method(self):
        self.__logger.debug("Setting payment method")
        method_input = self.__browser.get_element_by_css('input[name=settle_gubun][value="2"]')
        self.__browser.execute_script('arguments[0].click();', method_input)

    def __set_phones(self, phone='010-6275-2045'):
        self.__logger.debug("Setting receiver phone number")
        phone = phone.split('-')
        self.__browser.execute_script(
            f"document.getElementsByName('orphone1')[0].value = '{phone[0]}'")
        self.__browser.get_element_by_name('orphone2').send_keys(phone[1])
        self.__browser.get_element_by_name('orphone3').send_keys(phone[2])
        self.__browser.execute_script(
            f"document.getElementsByName('revhp1')[0].value = '{phone[0]}'")
        self.__browser.get_element_by_name("revhp2").send_keys(phone[1])
        self.__browser.get_element_by_name('revhp3').send_keys(phone[2])
        self.__browser.get_element_by_name('phone2').send_keys('0000')
        self.__browser.get_element_by_name('phone3').send_keys('0000')
        self.__browser.get_element_by_name('revphone2').send_keys('0000')
        self.__browser.get_element_by_name('revphone3').send_keys('0000')

    def __set_payment_mobile(self, phone='010-6275-2045'):
        self.__logger.debug("Setting payment phone number")
        phone = phone.split('-')
        if len(phone) == 0:
            self.__logger.info("Payment phone isn't set as it isn't provided")
            return
        self.__browser.execute_script(
            f"document.getElementsByName('virhp1')[0].value = '{phone[0]}'")
        self.__browser.get_element_by_name('virhp2').send_keys(phone[1])
        self.__browser.get_element_by_name('virhp3').send_keys(phone[2])

    def __set_purchase_date(self, purchase_date):
        if purchase_date and self.__is_purchase_date_valid(purchase_date):
            date_str = purchase_date.strftime('%Y-%m-%d')
            self.__browser.execute_script(
                f"document.getElementById('sale_date').value = '{date_str}'")

    def __set_purchase_order_id(self, purchase_order_id):
        self.__logger.debug("Setting purchase order ID")
        adapted_po_id = purchase_order_id.replace('-', 'ㅡ')
        self.__browser.get_element_by_name('revname').send_keys(adapted_po_id)

    def __set_receiver_address(self, address={
            'zip': '08584',
            'address_1': '서울특별시 금천구 두산로 70 (독산동)',
            'address_2': '291-1번지 현대지식산업센터  A동 605호'}):
        self.__logger.debug("Setting shipment address")
        self.__browser.execute_script("$('#deli_gubun2').click()")
        self.__browser.execute_script(
            f"$('[name=zip1]').val(\"{address['zip'][:2]}\");")
        self.__browser.execute_script(
            f"$('[name=zip2]').val(\"{address['zip'][2:]}\");")
        self.__browser.execute_script(
            f"$('[name=addr1]').val(\"{address['address_1']}\");")
        self.__browser.get_element_by_name('addr2').send_keys(address['address_2'])

    def __set_tax_info(self, tax_id=(123, 34, 26780)):
        self.__logger.debug("Setting counteragent tax information")
        if tax_id == ('', '', ''): # No company
            self.__browser.execute_script("$('input[name=tax_gubun][value=\"0\"]').click()")
        else:
            self.__browser.execute_script("$('input[name=tax_gubun][value=\"1\"]').click()")
            # self.__browser.execute_script(
            #     "document.getElementById('tTaxGubun1').value = '2'")
                
            tax_l_gubun = self.__browser.get_element_by_name('tax_l_gubun')
            # self.__browser.execute_script("arguments[0].click()", tax_l_gubun)
            self.__browser.execute_script("arguments[0].value = 2", tax_l_gubun)
            self.__browser.execute_script("chk_l_gubun();")
            # tTaxGubun1 = self.__browser.get_element_by_name('tax_l_gubun')
            # tTaxGubun1.click()
            # tTaxGubun1.send_keys(Keys.DOWN)
            # tTaxGubun1.send_keys(Keys.DOWN)
            # tTaxGubun1.send_keys(Keys.RETURN)
            self.__browser.get_element_by_name('tax_b_num1').send_keys(tax_id[0])
            self.__browser.get_element_by_name('tax_b_num2').send_keys(tax_id[1])
            self.__browser.get_element_by_name('tax_b_num3').send_keys(tax_id[2])

    def __submit_order(self):
        self.__logger.info("Submitting the order")
        self.__browser.execute_script("Submit()")
        try:
            self.__logger.debug('Waiting for order completion page')
            self.__browser.wait_for_url('https://atomy.kr/center/c_sale_ok.asp')
        except Exception as ex:
            self.__logger.warning("Couldn't get order completion page")
            raise Exception(ex)
            

        self.__logger.debug("Order completion page is loaded.")
        return self.__get_po_params()
        

    def __get_po_params(self):
        self.__logger.debug('Looking for purchase order number')
        po_id = None
        try:
            po_id_node = self.__browser.get_element_by_css(
                'font[color="#FF0000"] strong')
            po_id = po_id_node.text
                
        except Exception as ex:
            raise Exception("Couldn't get PO number", ex)

        self.__logger.debug('Looking for account number to pay')
        for attempt in range(1, 4): # Let's try to get account number several times
            divs = self.__browser.find_elements_by_css_selector('div[align="center"]')
            bank_account = None
            for div in divs:
                match = re.search(r'입금계좌번호\s+:\s+(\d+)', div.text)
                if match:
                    bank_account = match.groups()[0]
                    break
            if bank_account:
                return po_id, bank_account
            self.__logger.warning("Couldn't find account number at attempt %d.", attempt)
            sleep(5)
        self.__logger.warning("Gave up trying")  
        raise Exception("Couldn't find account number to pay to")
