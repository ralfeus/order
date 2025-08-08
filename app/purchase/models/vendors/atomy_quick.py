"""Fills and submits purchase order at Atomy
using quick order"""

from functools import reduce
from time import sleep
from typing import Any, Optional

from app.models.address import Address
from app.purchase.models.company import Company
from app.purchase.models.purchase_order import PurchaseOrder
from app.tools import get_html, try_perform
from utils.atomy import atomy_login2
from datetime import date, datetime, timedelta
import json
import logging
from pytz import timezone
import re
from playwright.sync_api import Locator, Page, expect, sync_playwright

from app import db
from exceptions import (
    AtomyLoginError,
    NoPurchaseOrderError,
    ProductNotAvailableError,
    PurchaseOrderError,
)
from app.orders.models.order_product import OrderProduct, OrderProductStatus
from app.purchase.models import PurchaseOrderStatus
from . import PurchaseOrderVendorBase

URL_BASE = "https://kr.atomy.com"
URL_NETWORK_MANAGER = "http://localhost:5001"
URL_SUFFIX = "_siteId=kr&_deviceType=pc&locale=ko-KR"
ERROR_FOREIGN_ACCOUNT = "해외법인 소속회원은 현재 소속국가 홈페이지에서 판매중인 상품을 주문하실 수 없습니다."
ERROR_OUT_OF_STOCK = "해당 상품코드의 상품은 품절로 주문이 불가능합니다"


ORDER_STATUSES = {
    "Order Placed": PurchaseOrderStatus.posted,
    "Unpaid Deadline": PurchaseOrderStatus.payment_past_due,
    "Shipping": PurchaseOrderStatus.paid,
    "Processing order": PurchaseOrderStatus.paid,
    "Shipped": PurchaseOrderStatus.shipped,
    "Order Completed": PurchaseOrderStatus.delivered,
    "Cancel Order": PurchaseOrderStatus.cancelled,
}

def try_click(object, execute_criteria, retries=3):
    exception = Exception(f"Failed to click the object after {retries} retries.")
    for _ in range(retries):
        try:
            object.click()
            execute_criteria()
            sleep(.7)
            return
        except Exception as e:
            print(f"Retrying click on {object}")
            exception = e
    raise exception

def fill(object: Locator, data: str):
    object.fill(data)
    expect(object).to_have_value(data)

def find_address(page: Page, base_address: str):
    page.locator('#lyr_pay_sch_bx33').fill(base_address)  # Base address
    page.locator('button[address-role="search-button"]').click()
    page.locator('button[address-role="select-button"]').click()

class AtomyQuick(PurchaseOrderVendorBase):
    """Manages purchase order at Atomy via quick order"""

    __purchase_order: PurchaseOrder = None  # type: ignore
    
    def __init__(
        self,
        browser=None,
        logger: Optional[logging.Logger] = None,
        config: dict[str, Any] = {},
    ):
        super().__init__()
        log_level = None
        if logger:
            log_level = logger.level
        else:
            if config:
                log_level = config["LOG_LEVEL"]
            else:
                log_level = logging.INFO
        logging.basicConfig(level=log_level)
        logger = logging.getLogger("AtomyQuick")
        logger.setLevel(log_level)  # type: ignore
        self.__original_logger = self._logger = logger
        self._logger.info(logging.getLevelName(self._logger.getEffectiveLevel()))
        self.__config: dict[str, Any] = config

    def __str__(self):
        return "Atomy - Quick order"

    def post_purchase_order(
        self, purchase_order
    ) -> tuple[PurchaseOrder, dict[str, str]]:
        """Posts a purchase order to Atomy based on provided purchase order data

        :param purchase_order:PurchaseOrder purchase order to be posted
        :returns: tuple[PurchaseOrder, dict[str, str]] posted purchase order
            and the list of products that couldn't be ordered"""
        self._logger = self.__original_logger.getChild(purchase_order.id)
        # First check whether purchase date set is in acceptable bounds
        if not self.__is_purchase_date_valid(purchase_order.purchase_date):
            if purchase_order.purchase_date < datetime.now().date():
                raise PurchaseOrderError(
                    purchase_order,
                    self,
                    "Can't create a purchase order. The purchase date is in the past",
                )
            self._logger.info(
                "Skip <%s>: purchase date is %s",
                purchase_order.id,
                purchase_order.purchase_date,
            )
            return purchase_order, {}
        self.__purchase_order = purchase_order
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                proxy={
                    "server": f"socks5://{self.__config['SOCKS5_PROXY']}"
                } if self.__config.get('SOCKS5_PROXY') else None) 
            # browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = browser.new_page()
            try:
                page.set_viewport_size({"width": 1420, "height": 1080})

                self.__login(page, purchase_order)
                self.__init_quick_order(page)
                ordered_products, unavailable_products = self.__add_products(
                    page, purchase_order.order_products
                )
                self.__set_purchase_date(page, purchase_order.purchase_date)
                self.__set_receiver_mobile(page, purchase_order.contact_phone)
                self.__set_receiver_name(page, purchase_order)
                self.__set_receiver_address(page,
                    purchase_order.address,
                    purchase_order.payment_phone
                )
                self.__set_local_shipment(page, ordered_products)
                self.__set_payment_params(page, purchase_order)
                self.__set_tax_info(page, purchase_order)
                po_params = self.__submit_order(page)
                self._logger.info("Created order %s", po_params[0])
                purchase_order.vendor_po_id = po_params[0]
                purchase_order.payment_account = po_params[1]
                purchase_order.total_krw = po_params[2]
                db.session.flush() # type: ignore
                self._set_order_products_status(
                    ordered_products, OrderProductStatus.purchased
                )
                browser.close()
                return purchase_order, unavailable_products
            except AtomyLoginError as ex:
                self._logger.warning("Couldn't log on as a customer %s", str(ex.args))
                raise ex
            except PurchaseOrderError as ex:
                self._logger.warning(ex)
                if ex.retry:
                    self._logger.warning("Retrying %s", purchase_order.id)
                    return self.post_purchase_order(purchase_order)
                raise ex
            except Exception as ex:
                self._logger.exception("Failed to post an order %s", purchase_order.id)
                page.screenshot(path=f'failed-{purchase_order.id}.png')
                raise ex

    def __login(self, page: Page, purchase_order):
        logger = self._logger.getChild("__login")
        logger.info("Logging in as %s", purchase_order.customer.username)
        page.goto(f"{URL_BASE}/login")
        page.fill("#login_id", purchase_order.customer.username)
        page.fill("#login_pw", purchase_order.customer.password)
        page.click(".login_btn button")
        page.wait_for_load_state()
        logger.debug("Logged in as %s", purchase_order.customer.username)

    def __init_quick_order(self, page):
        """Initializes the quick order. Doesn't return anything but essential
        for order creation"""
        logger = self._logger.getChild("__init_quick_order")
        logger.info('Changing language')
        page.evaluate('overpass.util.setLanguage("en");')
        page.wait_for_load_state("networkidle")
        try:
            page.locator('button[layer-role="close-button"]').click()
        except Exception as e:
            pass  # No popup to close
        logger.info('Opening Quick Order')
        try_click(page.locator('a[href^="javascript:overpass.cart.regist"]'),
                  lambda: page.wait_for_load_state())
        
    def __register_cart(self, page: Page) -> None:
        """Registers the cart with the products to be ordered

        :returns str: cart number"""
        logger = self._logger.getChild("__register_cart")
        logger.info("Registering cart")
        page.locator('[cart-role="quick-cart-send"]').click()
        try_click(
            page.locator('[layer-role="close-button"]'),
            lambda: page.wait_for_selector('#schInput', state='detached'))

    def __get_order_details(self, page: Page) -> dict[str, Any]:
        page.wait_for_load_state('networkidle')
        ord_data = [ m.string 
            for m in [
                re.search(r"JSON.parse\((.*)\)", s.text_content() or '')
                for s in page.locator('script').all()
            ] if m != None
        ][0]
        vendor_po = re.search(r"saleNum.*?(\d+)", ord_data).group(1) #type: ignore
        payment_account = re.search(r"ipgumAccountNo.*?(\d+)", ord_data).group(1) #type: ignore
        total = re.search(r"ipgumAmt.*?(\d+)", ord_data).group(1) #type: ignore
        return {
            "vendor_po": vendor_po,
            "payment_account": payment_account,
            "total_price": total,
        }

    def __add_products(self, page, order_products: list[OrderProduct]
            ) -> tuple[list[tuple[OrderProduct, str]], dict[str, str]]:
        """Adds products to be purchased.
        :param order_products: products to be ordered
        :type order_products: list[OrderProduct]
        :returns: list of tuples of ordered products and their entry in the cart
                  and dictionary of products that unavailable along with unavailability reason
        :rtype: tuple[list[tuple[OrderProduct, str]], dict[str, str]]
        """
        logger = self._logger.getChild("__add_products()")
        logger.info("Adding products")
        ordered_products = []
        unavailable_products = {}
        # Open the product search form
        sleep(3)
        try_click(page.locator('button[quick-form-button="search"]'),
                  lambda: page.wait_for_selector('#schInput', timeout=5000))

        for op in order_products:
            logger.info("Adding product %s", op.product_id)
            if not op.product.purchase:
                logger.warning(
                    "The product %s is exempted from purchase", op.product_id
                )
                continue
            if op.quantity <= 0:
                logger.warning(
                    "The product %s has wrong quantity %s", op.product_id, op.quantity
                )
                continue
            try:
                product_id = op.product_id.zfill(6)
                if not self.__is_product_allowed(page, product_id):
                    raise ProductNotAvailableError(
                        product_id, 
                        f"The product {product_id} is not allowed for user {self.__purchase_order.customer.username}")
                product_object, product_info = self.__get_product_by_id(page, product_id)
                product_object.fill(str(op.quantity))

                op.product.separate_shipping = bool(
                    int(product_info.get("isIndividualDelivery") or 0)
                )
                ordered_products.append((op,))
                logger.info("Added product %s", op.product_id)
            except ProductNotAvailableError as ex:
                logger.warning(
                    "Product %s is not available: %s", ex.product_id, ex.message
                )
                unavailable_products[ex.product_id] = ex.message
            except PurchaseOrderError as ex:
                raise ex
            except Exception:
                logger.exception("Couldn't add product %s", op.product_id)
        
        if len(ordered_products) == 0:
            raise PurchaseOrderError(
                self.__purchase_order,
                self,
                f"No available products are in the PO. Unavailable products:\n{unavailable_products}",
            )
        # Register the cart with the products to be ordered
        self.__register_cart(page)
        # Set the cart number in the goods list
        return ordered_products, unavailable_products

    def __get_product_by_id(self, page: Page, product_id):
        '''Gets a product or a specific product option by its ID'''
        logger = self._logger.getChild("__get_product_by_id")
        logger.debug("Getting product %s by ID", product_id)
        fill(page.locator('#schInput'), product_id)
        logger.debug("Set '%s' to the search field", product_id)
        try_click(page.locator('#schBtn'),
            lambda: page.wait_for_selector('#goodsList'))
        sleep(.7)
        product = page.locator('.lyr-pay-gds__item > input[data-goodsinfo]')
        if product.count() == 0:
            # No product was found
            raise ProductNotAvailableError(product_id, "Not found")
        product_info_attr = product.get_attribute('data-goodsinfo')
        product_info = json.loads(product_info_attr) #type: ignore
        button = page.locator('button[cart-role="btn-solo"]')
        if button.count() > 0: 
            # There are no options
            add_button = page.locator('//div[contains(@class, "item_top")]/button[em[text()="Add"]]')
            if add_button.is_disabled():
                raise ProductNotAvailableError(product_id)
            try_click(
                add_button, 
                lambda: page.wait_for_selector(f'[goods-cart-role="{product_id}"]'))
            result = page.locator(f'[goods-cart-role="{product_id}"] #selected-qty1')
        else:
            # There are options
            base_product_id = product_info["goodsNo"]
            result = self.__get_product_option(page, base_product_id, product_id)
        return result, product_info

    def __is_product_allowed(self, page, product_id):
        '''Checks whether product is allowed'''
        logger = self._logger.getChild("__is_product_allowed")
        logger.debug("Checking whether product %s allowed", product_id)
        result = page.evaluate(f"""
            async () => {{
                const res = await fetch('{URL_BASE}/cart/checkPurchaseRestrirction', {{
                    method: 'POST',
                    headers: {{'content-type': 'application/json'}},
                    body: '{{"goodsNoNmList":{{"{product_id}":""}}}}'
                }});
                return await res.ok
            }}
        """) 
        return result

    def __get_product_option(self, page, base_product_id, option_id):
        try_click(page.locator('button[option-role="opt-layer-btn"]'),
                    lambda: page.wait_for_selector('#gds_opt_0'))
        # base_product_id = page.locator('.lyr-gd__num').text_content()
        result = page.evaluate(f"""
            async () => {{
                const res = await fetch('{URL_BASE}/goods/itemStatus', {{
                    method: 'POST',
                    headers: {{'content-type': 'application/x-www-form-urlencoded'}},
                    body: 'goodsNo={base_product_id}&goodsTypeCd=101'
                }});
                return await res.json()
            }}
        """)
        option = [o for o in list(result.values()) if o['materialCode'] == option_id][0]
        option_list_loc = page.locator('div[option-role="item-option-list"]')
        product_loc = page.locator(f'//li[@goods-cart-role="{base_product_id}" and div[@class="lyr-gd__opt"]]') \
            .filter(has_text=option["optValNm1"])
        try_click(page.locator('button[aria-controls="pay-gds__slt_0"]').first,
                    lambda: option_list_loc.wait_for(state='visible'))
        if option.get('optValNm2') == None:
            try_click(page.locator(f'//a[.//span[normalize-space(text()) = "{option["optValNm1"]}"]]'),
                    lambda: page.wait_for_selector('#cart'))
        else:
            try_click(page.locator(f'//a[.//span[normalize-space(text()) = "{option["optValNm1"]}"]]'),
                    lambda: page.wait_for_selector('.btn_opt_slt[item-box="1"]'))
            try_click(page.locator('button[aria-controls="pay-gds__slt_0"]').last,
                    lambda: option_list_loc.last.wait_for(state='visible'))
            try_click(page.locator(f'//a[.//span[normalize-space(text()) = "{option["optValNm2"]}"]]'),
                    lambda: page.wait_for_selector('#cart'))
            product_loc = product_loc.filter(has_text=option["optValNm2"])
        try_click(page.locator('#cart'), 
                    lambda: product_loc.wait_for(state='visible'))
        return product_loc.locator('input#selected-qty1')

    def __is_purchase_date_valid(self, purchase_date):
        tz = timezone("Asia/Seoul")
        today = datetime.now().astimezone(tz)
        days_back = 3 if today.weekday() < 2 else 2
        days_forth = 2 if today.weekday() == 5 else 1
        min_date = (today - timedelta(days=days_back)).date()
        max_date = (today + timedelta(days=days_forth)).date()
        return purchase_date is None or (
            purchase_date >= min_date and purchase_date <= max_date
        )

    def __set_purchase_date(self, page: Page, sale_date: date):
        logger = self._logger.getChild("__set_purchase_date")
        if sale_date and self.__is_purchase_date_valid(sale_date):
            sale_date_str = sale_date.strftime('%Y-%m-%d')
            try_click(page.locator(f'ul.slt-date input[value="{sale_date_str}"] + label'),
                  lambda: expect(page.locator(
                      f'ul.slt-date input[value="{sale_date_str}"]'))
                      .to_be_checked())
            logger.info("Purchase date is set to %s", sale_date_str)
        else:
            logger.info("Purchase date is left default")

    def __set_local_shipment(
        self, page: Page,
        ordered_products: list[tuple[OrderProduct, str]],
    ):
        logger = self._logger.getChild("__set_local_shipment")
        logger.debug("Set local shipment")
        free_shipping_eligible_amount = reduce(
            lambda acc, op: (
                acc + (op[0].price * op[0].quantity)
                if not op[0].product.separate_shipping
                else 0
            ),
            ordered_products,
            0,
        )
        local_shipment = (
            free_shipping_eligible_amount
            < self.__config["FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD"]
        )
        if local_shipment:
            logger.debug("Setting combined shipment")
            try_perform(lambda: self.__set_combined_shipping(page), logger=logger)
            logger.debug("Combined shipment is set")
        else:
            logger.debug("No combined shipment is needed")

    def __set_combined_shipping(self, page: Page):
        combined_shipping = page.locator('label[for="pay-dlv_ck0_1"]')
        if combined_shipping.count() > 0:
            try_click(combined_shipping,
                lambda: page.wait_for_selector('[layer-role="close-button"]'))
            try_click(page.locator('[layer-role="close-button"]'),
                lambda: page.wait_for_selector('[layer-role="close-button"]', state='detached'))
            if not page.locator('#pay-dlv_ck0_1').is_checked():
                raise Exception("Combined shipping is not set")

    def __set_receiver_name(self, page: Page, purchase_order: PurchaseOrder) -> None:
        logger = self._logger.getChild("__set_receiver_name")
        logger.debug("Setting recipient's name")
        order_id_parts = purchase_order.id[8:].split("-")
        parts = {
            "id0": order_id_parts[0],
            "id1": order_id_parts[1],
            "id2": order_id_parts[2][1:],
            "company": purchase_order.company,
        }
        rcpt_name = (
            self.__config.get("ATOMY_RECEIVER_NAME_FORMAT") or "{company} {id1}"
        ).format(**parts)
        page.locator("#psn-txt_0_0").fill(rcpt_name)
        expect(page.locator("#psn-txt_0_0")).to_have_value(rcpt_name)
        logger.debug(f"Recipient's name set to {rcpt_name}")


    def __set_receiver_mobile(self, page: Page, phone="     "):
        logger = self._logger.getChild("__set_receiver_mobile")
        logger.debug("Setting receiver phone number to %s", phone)
        fill(page.locator("#psn-txt_1_0"), phone.replace('-', ''))

    def __set_receiver_address(self, page: Page, address: Address, phone: str):
        logger = self._logger.getChild("__set_receiver_address")
        logger.debug("Setting recipient's address")
        try_click(
            page.locator('button[data-owns="lyr_pay_addr_lst"]'),
            lambda: page.locator('#btnOrderDlvpReg').wait_for(timeout=5000))
        addresses = page.locator('#dlvp_list > dl.lyr-address')
        if addresses.count() > 0:
            logger.debug("Found %s addresses.", addresses.count())
        else:
            logger.debug("No addresses found, creating a new one.")
            try_click(page.locator('#btnOrderDlvpReg'),
                lambda: page.wait_for_selector('div.lyr-pay_addr_add'))
            page.fill('#dlvpNm', address.name)
            expect(page.locator('#dlvpNm')).to_have_value(address.name)
            page.fill('#cellNo', phone.replace('-', ''))
            expect(page.locator('#cellNo')).to_have_value(phone.replace('-', ''))            
            page.locator('#btnAdressSearch').click()
            find_address(page, address.address_1)  # base address
            fill(page.locator('#dtlAddr'), address.address_2)
            page.locator('#dtlAddr').dispatch_event('keyup')          
            page.locator('label[for="baseYn"]').click()
            try_click(page.locator('#btnSubmit'),
                lambda: page.wait_for_selector('div.lyr-pay_addr_add', state='detached'))
        try_click(page.locator('#dlvp_list > dl.lyr-address').first,
                  lambda: page.wait_for_selector('#btnLyrPayAddrLstClose', state='detached'))

    def __set_payment_params(
        self, page: Page, po: PurchaseOrder
    ):
        logger = self._logger.getChild("__set_payment_params")
        logger.debug("Setting payment parameters")
        # Set the payment method
        logger.debug("Setting payment method...")
        page.locator('#mth-tab_3').click()
        page.locator('#mth-cash-slt_0').select_option(po.company.bank_id) 
        # Set the payment mobile
        logger.debug("Setting payment mobile...")
        page.locator('#mth-cash-txt_0').fill(po.payment_phone)
        logger.debug("Payment parameters are set")

    def __set_tax_info(self, page: Page, purchase_order: PurchaseOrder):
        logger = self._logger.getChild("__set_tax_info")
        logger.info("Setting counteragent tax information")
        if purchase_order.company.tax_id != ("", "", ""):  # Company is taxable
            company = purchase_order.company
            if company.tax_simplified:
                logger.debug("Setting tax information for simplified tax invoice")
                page.locator('label[for="cash-mth-proof_rdo_1"]').click()
                confirm_button = page.locator('button[layer-role="confirm-button"]')
                try_click(page.locator('label[for="pay_important_ck_0"]'),
                    lambda: expect(confirm_button).to_be_enabled(), retries=5)
                confirm_button.click()
                logger.debug('Set usage purpose')
                page.locator('#cash-mth-proof-slt_0').select_option('cash-receipt_1')
                page.locator('#cash-mth-receipt_opr').fill('%s%s%s' % company.tax_id)
                page.locator('label[for="cash-mth-cash-btm_ck0"]').click()            
            else:
                logger.debug("Setting tax information for tax invoice")
                confirm_button = page.locator('button[layer-role="confirm-button"]')
                logger.debug("Switch to Tax Invoice")
                try_click(page.locator('label[for="cash-mth-proof_rdo_2"]'),
                        lambda: expect(confirm_button).to_be_attached())
                logger.debug("Close notice")
                try_click(page.locator('label[for="pay_important_ck_1"]'),
                        lambda: expect(confirm_button).to_be_enabled())
                try_click(confirm_button,
                        lambda: expect(confirm_button).not_to_be_attached())
                logger.debug("Select New")
                try_click(page.locator('label[for="cash-mth-taxes_rdo_1"]'),
                        lambda: page.wait_for_selector('#cash-mth-taxes-txt_0'))
                logger.debug("Fill data")
                fill(page.locator('#cash-mth-taxes-txt_0'), company.name) # Company Name
                fill(page.locator('#cash-mth-taxes-txt_1'), '%s%s%s' % company.tax_id) # Business Number
                fill(page.locator('#cash-mth-taxes-txt_2'), company.contact_person) # Representative name
                logger.debug("Find address")
                try_click(page.locator('#cash-btnAdressSearch'),
                        lambda: page.wait_for_selector('#lyr_pay_sch_bx33'))
                find_address(page, company.address.address_1)
                fill(page.locator('#cash-mth-taxes-txt_3_dtl'), company.address.address_2) # Detailed address
                fill(page.locator('#cash-mth-taxes-txt_4'), company.business_type) # Business status
                fill(page.locator('#cash-mth-taxes-txt_5'), company.business_category) # Business type
                fill(page.locator('#cash-mth-taxes-txt_6'), company.tax_phone) # Mobile
                fill(page.locator('#cash-mth-taxes-txt_7'), company.contact_person) # Manager
                fill(page.locator('#cash-mth-taxes-txt_8'), company.email) # E-mail
            logger.debug("Tax information is set")

    def __submit_order(self, page: Page):
        logger = self._logger.getChild("__submit_order")
        logger.info("Submitting the order")
        logger.debug("Agreeing to terms")
        page.locator('label[for="fxd-agr_ck_2502000478"]').click()
        logger.debug("Submitting order")
        page.locator('button[sheet-role="pay-button"]').click()
        page.wait_for_selector('.odrComp', timeout=60000)
        vendor_po = self.__get_order_details(page)
        logger.debug("Created order: %s", vendor_po)
        return (
            vendor_po["vendor_po"],
            vendor_po["payment_account"],
            vendor_po["total_price"],
        )

    def update_purchase_order_status(self, purchase_order: PurchaseOrder):
        logger = self._logger.getChild("update_purchase_order_status")
        logger.info("Updating %s status", purchase_order.id)
        logger.debug("Logging in as %s", purchase_order.customer.username)
        session = [{"Cookie": atomy_login2(
            purchase_order.customer.username,
            purchase_order.customer.password
        )}]
        logger.debug("Getting POs from Atomy...")
        vendor_purchase_orders = self.__get_purchase_orders(session)
        self._logger.debug("Got %s POs", len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            # logger.debug(str(o))
            if o["id"] == purchase_order.vendor_po_id:
                purchase_order.set_status(ORDER_STATUSES[o["status"]])
                return purchase_order

        raise NoPurchaseOrderError(
            "No corresponding purchase order for Atomy PO <%s> was found"
            % purchase_order.vendor_po_id
        )

    def update_purchase_orders_status(self, subcustomer, 
                                      purchase_orders: list[PurchaseOrder]):
        logger = self._logger.getChild("update_purchase_orders_status")
        logger.info("Updating %s POs status", len(purchase_orders))
        logger.debug("Attempting to log in as %s...", subcustomer.name)
        session = [{"Cookie": atomy_login2(
            purchase_orders[0].customer.username,
            purchase_orders[0].customer.password
        )}]
        logger.debug("Getting subcustomer's POs")
        vendor_purchase_orders = self.__get_purchase_orders(session)
        logger.debug("Got %s POs", len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            # logger.debug(str(o))
            if ORDER_STATUSES[o["status"]] == PurchaseOrderStatus.posted:
                logger.debug("Skipping PO %s", o["id"])
                continue
            filtered_po = [
                po for po in purchase_orders if po and po.vendor_po_id == o["id"]
            ]
            try:
                filtered_po[0].set_status(ORDER_STATUSES[o["status"]])
            except IndexError:
                logger.warning(
                    "No corresponding purchase order for Atomy PO <%s> was found",
                    o["id"],
                )

    def __get_purchase_orders(self, session_headers: list[dict[str, str]]):
        logger = self._logger.getChild("__get_purchase_orders")
        logger.debug("Getting purchase orders")
        res = get_html(
            url=f"{URL_BASE}/mypage/orderList?"
            + "psearchMonth=12&startDate=&endDate=&orderStatus=all&pageIdx=2&rowsPerPage=100",
            headers=session_headers + [{"Cookie": "KR_language=en"}],
        )

        orders = [
            {
                "id": element.cssselect("input[name='hSaleNum']")[0].attrib["value"],
                "status": element.cssselect("span.m-stat")[0].text.strip(),
            }
            for element in res.cssselect("div.my_odr_gds li")
        ]
        return orders