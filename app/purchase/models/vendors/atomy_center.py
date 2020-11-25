from app.orders.models import Subcustomer
from app.purchase.models import PurchaseOrder
from app.utils.browser import Browser, Keys
from . import PurchaseOrderVendorBase

class AtomyCenter(PurchaseOrderVendorBase):
    def __init__(self, browser=None, logger=None, config=None):
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
        self.__username = 'atomy1026'
        self.__password = '5714'

    def __str__(self):
        return "Atomy - Center"

    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        self.login()
        self.__open_order()
        self.__set_customer_id(purchase_order.customer_id)
        self.__set_purchase_date(purchase_order.purchase_date)
        self.__set_phones(purchase_order.contact_phone)
        ordered_products = self.__add_products(purchase_order.order_products)
        self.__set_receiver_address(purchase_order.address)
        self.__set_combined_shipment()
        self.__set_purchase_order_id(purchase_order.id)
        self.__set_payment_method()
        self.__set_payment_destination(purchase_order.bank_id)
        self.__set_payment_mobile(purchase_order.payment_phone)
        self.__set_tax_info(purchase_order.company.tax_id)
        po_params = self.__submit_order()
        purchase_order.vendor_po_id = po_params[0]
        purchase_order.payment_account = po_params[1]
        self._set_order_products_status(ordered_products, 'Purchased')
        return purchase_order

    def update_purchase_orders_status(self, customer: Subcustomer, customer_pos: list):
        pass

    def login(self):
        self.__browser.get('https://atomy.kr/center/login.asp')
        self.__browser.get_element_by_css('input[name="admin_id"]').send_keys(self.__username)
        password_input = self.__browser.get_element_by_css('input[name="password"]')
        password_input.send_keys(self.__username)
        password_input.send_keys(Keys.RETURN)

    def __open_order(self):
        self.__browser.get('https://atomy.kr/center/login.asp')

    def __set_customer_id(customer_id):
        self.__logger.info("PO: Setting customer ID")
        cust_no_input = self.__browser.get_element_by_id('cust_no')
        cust_no_input.send_keys(customer_id)
        cust_no_input.send_keys(Keys.RETURN)
