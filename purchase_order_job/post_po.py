"""Fills and submits purchase order at Atomy
using quick order"""

from functools import reduce
import os
from time import sleep
from typing import Any, Optional

from po_types import Config, OrderProduct, PurchaseOrder, Address
from datetime import date, datetime, timedelta
import json
import logging
from pytz import timezone
import re
from playwright.sync_api import Locator, Page, expect, sync_playwright

from exceptions import (
    AtomyLoginError,
    ProductNotAvailableError,
    PurchaseOrderError,
)

URL_BASE = "https://kr.atomy.com"
DATA_DIR = os.environ.get("DATA_DIR", "/data")

ERROR_BAD_ACCOUNT = "Unverified distributor cannot purchase."
ERROR_ADDRESS_EXISTS = "The same shipping address is already registered."
PRODUCTS_ADDED_TO_CART = 'The product has been added.'

def try_evaluate(page: Page, script: str, retries=3):
    logger = logging.root.getChild("try_evaluate()")
    exception = Exception(f"Failed to evaluate the script after {retries} retries.")
    ### Last resort debugging screenshot
    if __config.DEBUG_SCREENSHOTS:
        page.screenshot(
            path=f'{DATA_DIR}/{logger.name}-{datetime.now().strftime("%Y%m%d%H%M%S.%f")}.png',
            full_page=True)
    for _ in range(retries):
        try:
            return page.evaluate(script)
        except Exception as e:
            logger.debug("Retrying evaluation of the script")
            logger.debug(str(e))
            exception = e
            sleep(1)
    raise exception

def try_click(object: Locator, execute_criteria, retries=3, 
              base_logger: logging.Logger=logging.root):
    logger = base_logger.getChild("try_click()")
    exception = Exception(f"Failed to click the object after {retries} retries.")
    ### Last resort debugging screenshot
    if __config.DEBUG_SCREENSHOTS:
        object.page.screenshot(
            path=f'{DATA_DIR}/{logger.name}-{datetime.now().strftime("%Y%m%d%H%M%S.%f")}.png',
            full_page=True)
    for _ in range(retries):
        try:
            object.click()
            execute_criteria()
            sleep(.7)
            return
        except Exception as e:
            logger.debug(f"Retrying click on {object}")
            logger.debug(str(e))
            exception = e
    raise exception

def try_fill(object: Locator, data: str, retries: int=3, 
             base_logger: logging.Logger=logging.root):
    logger = base_logger.getChild("fill()")
    exception = Exception(f"Failed to fill the object {object} with value {data}"
                          f" after {retries} retries.")
    ### Last resort debugging screenshot
    if __config.DEBUG_SCREENSHOTS:
        object.page.screenshot(
            path=f'{DATA_DIR}/{logger.name}-{datetime.now().strftime("%Y%m%d%H%M%S.%f")}.png',
            full_page=True)
    for _ in range(retries):
        try:
            object.fill(data)
            expect(object).to_have_value(data)
            return
        except Exception as e:
            logger.debug(f"Retrying filling {object} with value {data}")
            logger.debug(str(e))
            exception = e
            sleep(1)
    raise exception

def find_address(page: Page, base_address: str):
    try_fill(page.locator('#lyr_pay_sch_bx33'), base_address)  # Base address
    try_click(page.locator('button[address-role="search-button"]'),
              lambda: page.wait_for_selector('[address-role="result"]'))
    found_addresses = page.locator('button[address-role="select-button"]')
    if found_addresses.count() < 1:
        raise Exception(f"The base address {base_address} is invalid")
    if found_addresses.count() > 1:
        raise Exception("More than one address found")
    try_click(found_addresses,
              lambda: page.wait_for_selector('[address-role="result"]', state='detached'))
    
def find_existing_address(page: Page, address: Address) -> Optional[Locator]:
    addresses = page.locator('#dlvp_list > dl.lyr-address').all()
    # print(f"Found {len(addresses)} addresses")
    for address_element in addresses:
        # print(f"Address: {address_element.get_attribute('data-recvr-post-no')}"
        #       f"         {address_element.get_attribute('data-recvr-base-addr')}"
        #       f"         {address_element.get_attribute('data-recvr-dtl-addr')}")
        if address_element.get_attribute('data-recvr-post-no') \
            and ((address_element.get_attribute('data-recvr-base-addr') or '') in address.address_1
                 or address.address_1 in (address_element.get_attribute('data-recvr-base-addr') or '')) \
            and ((address_element.get_attribute('data-recvr-dtl-addr') or '') in address.address_2
                 or address.address_2 in (address_element.get_attribute('data-recvr-dtl-addr') or '')):
            return address_element
    return None
    # data-dlvp-nm="Valentina" 
    # data-dlvp-memo="문 앞에 놓아주세요." 
    # data-recvr-post-no="15211" 
    # data-recvr-base-addr="경기도 안산시 단원구 석수동길 57" 
    # data-recvr-dtl-addr="302호" 
    # data-cell-no="010-7563-8479" 
    # data-deli-state="경기도" 
    # data-deli-city="안산시 단원구"

def create_address(page: Page, address: Address, phone: str):
    addresses_loc = page.locator('#dlvp_list > dl.lyr-address')
    existing_addresses_count = addresses_loc.count()
    try_click(page.locator('#btnOrderDlvpReg'),
        lambda: page.wait_for_selector('div.lyr-pay_addr_add'))
    try_fill(page.locator('#dlvpNm'), address.name)
    try_fill(page.locator('#cellNo'), phone.replace('-', ''))
    page.locator('#btnAdressSearch').click()
    find_address(page, address.address_1)  # base address
    # If the found base address is different than provided one
    # there is a chance it exists and just wasn't found
    found_base_address = page.locator('#baseAddr').text_content() or ''
    if not (
        found_base_address in address.address_1 or
        address.address_1 in found_base_address ):
        address.address_1 = found_base_address
        existing_address = find_existing_address(page, address)
        if existing_address:
            try_click(
                page.locator('//button[@id="btnSubmit"]/preceding-sibling::*[1]'),
                lambda: page.wait_for_selector('div.lyr-pay_addr_add', state='detached'))
            return existing_address
    try_fill(page.locator('#dtlAddr'), address.address_2)
    page.locator('#dtlAddr').dispatch_event('keyup')          
    try_click(page.locator('#btnSubmit'),
        lambda: page.wait_for_selector('div.lyr-pay_addr_add', state='detached'))
    while addresses_loc.count() == existing_addresses_count:
        sleep(1)
    return find_existing_address(page, address)

def get_receiver_name(purchase_order: PurchaseOrder, template: str) -> str:
    order_id_parts = purchase_order.id[8:].split("-")
    parts = {
        "id0": order_id_parts[0],
        "id1": order_id_parts[1],
        "id2": order_id_parts[2][1:],
        "company": purchase_order.company.name,
    }
    return template.format(**parts)

def update_address(address_element: Locator, name: str, detailed_address: str, 
                   parent_logger: logging.Logger):
    logger = parent_logger.getChild("atomy_quick.update_address_name")
    edit_window = address_element.page.locator('#lyr_pay_addr_add')
    try_click(address_element.locator('button[data-owns="lyr_pay_addr_edit"]'),
              lambda: expect(edit_window).to_be_visible())
    try_fill(edit_window.locator('#dlvpNm'), name)
    submit_button = edit_window.locator('#btnSubmit')
    if submit_button.is_disabled():
        logger.error("The detailed address is missing. Adding...")
        try_fill(edit_window.locator('#dtlAddr'), detailed_address)
        edit_window.locator('#dtlAddr').dispatch_event('keyup')          
    try_click(submit_button, 
              lambda: expect(edit_window).not_to_be_attached())
    expect(address_element.locator('dt>b')).to_have_text(name)

__config: Config
def init_config():
    with open('config.json', 'r') as f:
        global __config 
        __config = Config(**json.load(f))
    __config.DEBUG_SCREENSHOTS = bool(int(os.environ.get("DEBUG_SCREENSHOTS", "0")))
    __config.BROWSER_URL = os.environ.get('BROWSER_URL')
    __config.LOG_LEVEL = int(os.environ.get('LOG_LEVEL', logging.INFO))

_logger = logging.getLogger("post_po_job")
def init_logging():
    _logger.setLevel(__config.LOG_LEVEL)
    _logger.info("Log level: %s", __config.LOG_LEVEL)
    
po: PurchaseOrder
page: Page
def post_purchase_order(purchase_order: PurchaseOrder, retries: int=3
    ) -> tuple[PurchaseOrder, dict[str, str]]:
    """Posts a purchase order to Atomy based on provided purchase order data

    :param PurchaseOrder purchase_order: purchase order to be posted
    :param int retries: number of retries in case of failure

    :returns tuple[PurchaseOrder, dict[str, str]]: posted purchase order
        and the list of products that couldn't be ordered"""
    global po, page
    po = purchase_order
    init_config()
    init_logging()
    logger = logging.root.getChild(purchase_order.id)
    # First check whether purchase date set is in acceptable bounds
    if not __is_purchase_date_valid(purchase_order.purchase_date):
        if purchase_order.purchase_date and \
           purchase_order.purchase_date < datetime.now().date():
            raise PurchaseOrderError(
                purchase_order,
                f"The purchase date {purchase_order.purchase_date} is not available"
            )
        logger.info(
            "Skip <%s>: purchase date is %s",
            purchase_order.id,
            purchase_order.purchase_date,
        )
        return purchase_order, {}
    logger.debug("Initializing playwright")
    with sync_playwright() as p:
        if __config.BROWSER_URL:
            logger.debug("Connecting to the browser")
            browser = p.chromium.connect_over_cdp(__config.BROWSER_URL)
        else:
            logger.debug("Starting the browser")
            browser = p.chromium.launch(
                headless=True,
                # proxy={
                #     "server": f"socks5://{__config['SOCKS5_PROXY']}"
                # } if __config.get('SOCKS5_PROXY') else None) 
            )
        page = browser.new_page()
        try:
            page.set_viewport_size({"width": 1420, "height": 1080})

            __login(purchase_order.customer.username, purchase_order.customer.password)
            __init_quick_order(purchase_order, page)
            ordered_products, unavailable_products = __add_products()
            __set_purchase_date()
            __set_receiver_mobile(purchase_order.contact_phone)
            __set_receiver_name()
            __set_receiver_address()
            __set_local_shipment(ordered_products)
            __set_payment_params()
            __set_tax_info()
            po_params = __submit_order()
            logger.info("Created order %s", po_params[0])
            purchase_order.vendor_po_id = po_params[0]
            purchase_order.payment_account = po_params[1]
            purchase_order.total_krw = po_params[2]
            return purchase_order, unavailable_products
        except AtomyLoginError as ex:
            logger.warning("Couldn't log on as a customer %s", str(ex.args))
            raise ex
        except PurchaseOrderError as ex:
            logger.warning(ex)
            if ex.screenshot:
                page.screenshot(path=f'{DATA_DIR}/failed-{purchase_order.id}.png', full_page=True)
            if ex.retry and retries > 0:
                retries -= 1
                logger.warning("Retrying %s", purchase_order.id)
            else:
                raise ex
        except Exception as ex:
            logger.exception("Failed to post an order %s", purchase_order.id)
            page.screenshot(path=f'{DATA_DIR}/failed-{purchase_order.id}.png', full_page=True)
            raise ex
        finally:
            browser.close()

    # Only way to reach here is the retry is needed
    return post_purchase_order(purchase_order)

def __login(username: str, password: str):
    logger = _logger.getChild("__login")
    logger.info("Logging in as %s", username)
    page.goto(f"{URL_BASE}/login")
    page.wait_for_load_state()
    try_fill(page.locator("#login_id"), username, base_logger=logger)
    try_fill(page.locator("#login_pw"), password, base_logger=logger)
    try_click(page.locator(".login_btn button"), 
              lambda: page.wait_for_load_state(), base_logger=logger)
    logger.debug("Logged in as %s", username)

def __init_quick_order(po: PurchaseOrder, page: Page) -> None:
    """Initializes the quick order. Doesn't return anything but essential
    for order creation"""
    logger = _logger.getChild("__init_quick_order")
    logger.info('Changing language')
    try_evaluate(page, 'overpass.util.setLanguage("en");')
    page.wait_for_load_state("networkidle")
    try:
        page.locator('button[layer-role="close-button"]').click()
    except Exception as e:
        pass  # No popup to close
    logger.info('Opening Quick Order')
    try_click(page.locator('a[href^="javascript:overpass.cart.regist"]'),
                lambda: page.wait_for_load_state())
    if page.locator(f'//p[@layer-role="message" and text() = "{ERROR_BAD_ACCOUNT}"]').count() > 0:
        raise PurchaseOrderError(po, ERROR_BAD_ACCOUNT)
    
def __register_cart(po: PurchaseOrder, page: Page) -> None:
    """Registers the cart with the products to be ordered

    :returns str: cart number"""
    logger = _logger.getChild("__register_cart")
    logger.info("Registering cart")
    try_click(page.locator('[cart-role="quick-cart-send"]'),
        lambda: page.wait_for_selector('button[layer-role="close-button"]'),
        base_logger=logger)
    message = page.locator('//p[@layer-role="message"]').all_text_contents()
    if PRODUCTS_ADDED_TO_CART not in message:
        raise PurchaseOrderError(po, message, screenshot=True)
    try_click(
        page.locator('[layer-role="close-button"]'),
        lambda: page.wait_for_selector('#schInput', state='detached'),
        base_logger=logger)

def __get_order_details(page: Page) -> dict[str, Any]:
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

def __add_products() -> tuple[list[tuple[OrderProduct, str]], dict[str, str]]:
    """Adds products to be purchased.
    :param order_products: products to be ordered
    :type order_products: list[OrderProduct]
    :returns: list of tuples of ordered products and their entry in the cart
                and dictionary of products that unavailable along with unavailability reason
    :rtype: tuple[list[tuple[OrderProduct, str]], dict[str, str]]
    """
    logger = _logger.getChild("__add_products()")
    logger.info("Adding products")
    ordered_products = []
    unavailable_products = {}
    # Open the product search form
    sleep(3)
    try:
        try_click(page.locator('button[quick-form-button="search"]'),
                lambda: page.wait_for_selector('#schInput', timeout=10000),
                base_logger=logger)
    except:
        # At this point there should be no issue
        # Therefore the PO will be retried
        logger.error("Couldn't open the product search form")
        raise PurchaseOrderError(po,
            "Couldn't open the product search form", retry=True, screenshot=True)
    for order_product in po.order_products:
        op = order_product
        logger.info("Adding product %s", op.product_id)
        if not op.purchase:
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
            if not __is_product_allowed(page, product_id):
                raise ProductNotAvailableError(
                    product_id, 
                    f"The product {product_id} is not allowed for user {po.customer.username}")
            product_object, product_info = __get_product_by_id(page, product_id)
            try_fill(product_object, str(op.quantity))

            op.separate_shipping = bool(
                int(product_info.get("isIndividualDelivery") or 0)
            )
            ordered_products.append((op,))
            logger.debug("Added product %s", op.product_id)
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
            po,
            f"No available products are in the PO. Unavailable products:\n{unavailable_products}",
        )
    # Register the cart with the products to be ordered
    __register_cart(po, page)
    # Set the cart number in the goods list
    return ordered_products, unavailable_products

def __get_product_by_id(page: Page, product_id, 
            _logger: logging.Logger=logging.root):
    '''Gets a product or a specific product option by its ID'''
    logger = _logger.getChild("__get_product_by_id")
    logger.debug("Getting product %s by ID", product_id)
    try_fill(page.locator('#schInput'), product_id)
    logger.debug("Set '%s' to the search field", product_id)
    page.locator('#schBtn').click()
    sleep(1)
    expect(page.locator('#goodsList')).to_be_visible()
    product = page.locator('.lyr-pay-gds__item > input[data-goodsinfo]')
    product_count = product.count()
    # print(product_count)
    if product_count == 0:
        # No product was found
        raise ProductNotAvailableError(product_id, "Not found")
    if product_count > 1 and product_count < 15:
        raise ProductNotAvailableError(product_id, "More than one product found")
    if product_count >= 15:
        logger.info("The result isn't shown yet")
        while product.count() >= 15:
            sleep(1)
    product_info_attr = product.get_attribute('data-goodsinfo')
    product_info = json.loads(product_info_attr) #type: ignore
    button = page.locator('button[cart-role="btn-solo"]')
    if button.count() > 0: 
        # There are no options
        add_button = page.locator('//div[contains(@class, "item_top")]/button[em[text()="Add"]]')
        if add_button.is_disabled():
            raise ProductNotAvailableError(product_id)
        logger.debug("The product has no options. Adding to cart")
        try_click(
            add_button, 
            lambda: page.wait_for_selector(f'[goods-cart-role="{product_id}"]'))
        result = page.locator(f'[goods-cart-role="{product_id}"] #selected-qty1')
    else:
        # There are options
        logger.debug("The product has options")
        base_product_id = product_info["goodsNo"]
        result = __get_product_option(page, base_product_id, product_id, logger)
    return result, product_info

def __is_product_allowed(page, product_id, 
            _logger: logging.Logger=logging.root) -> bool:
    '''Checks whether product is allowed'''
    logger = _logger.getChild("__is_product_allowed")
    logger.debug("Checking whether product %s allowed", product_id)
    result = try_evaluate(page, f"""
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

def __get_product_option(page: Page, base_product_id, option_id, 
                            base_logger: logging.Logger=logging.root):
    logger = base_logger.getChild("__get_product_option")
    option_button = page.locator('button[option-role="opt-layer-btn"]')
    if option_button.is_disabled():
        raise ProductNotAvailableError(base_product_id)
    logger.debug("Getting available options")
    try_click(option_button,
                lambda: page.wait_for_selector('#gds_opt_0'))
    # base_product_id = page.locator('.lyr-gd__num').text_content()
    result = try_evaluate(page, f"""
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
    logger.debug("Selecting option %s", option["optValNm1"])
    try_click(page.locator('button[aria-controls="pay-gds__slt_0"]').first,
                lambda: option_list_loc.wait_for(state='visible'))
    if option.get('optValNm2') == None:
        logger.debug("The product has 1 option. Adding to cart")
        try_click(page.locator(f'//a[.//span[normalize-space(text()) = "{option["optValNm1"].strip()}"]]'),
                lambda: page.wait_for_selector('#cart'))
    else:
        logger.debug("The product has 2 options")
        try_click(page.locator(f'//a[.//span[normalize-space(text()) = "{option["optValNm1"].strip()}"]]'),
                lambda: page.wait_for_selector('.btn_opt_slt[item-box="1"]'))
        try_click(page.locator('button[aria-controls="pay-gds__slt_0"]').last,
                lambda: option_list_loc.last.wait_for(state='visible'))
        logger.debug("Selected 2nd option. Adding to cart")
        try_click(page.locator(f'//a[.//span[normalize-space(text()) = "{option["optValNm2"].strip()}"]]'),
                lambda: page.wait_for_selector('#cart'))
        product_loc = product_loc.filter(has_text=option["optValNm2"])
    try_click(page.locator('#cart'), 
                lambda: product_loc.wait_for(state='visible'))
    return product_loc.locator('input#selected-qty1')

def __is_purchase_date_valid(purchase_date: Optional[date]) -> bool:
    tz = timezone("Asia/Seoul")
    today = datetime.now().astimezone(tz)
    days_back = 3 if today.weekday() < 2 else 2
    days_forth = 2 if today.weekday() == 5 else 1
    min_date = (today - timedelta(days=days_back)).date()
    max_date = (today + timedelta(days=days_forth)).date()
    return purchase_date is None or (
        purchase_date >= min_date and purchase_date <= max_date
    )

def __set_purchase_date():
    logger = _logger.getChild("__set_purchase_date")
    logger.debug("Setting purchase date")
    sale_date = po.purchase_date
    if sale_date:
        sale_date_str = sale_date.strftime('%Y-%m-%d')
        sale_date_loc = page.locator(f'ul.slt-date input[value="{sale_date_str}"] + label')
        if sale_date_loc.count():
            try:
                try_click(sale_date_loc,
                    lambda: expect(page.locator(
                        f'ul.slt-date input[value="{sale_date_str}"]'))
                        .to_be_checked())
            except Exception as e:
                if "intercepts pointer events" in str(e):
                    logger.warning("An unexpected popup is shown. "
                                    "The PO will be retried")
                    raise PurchaseOrderError(po, 
                        message=str(e), retry=True)
                raise PurchaseOrderError(po,
                    message=f"Couldn't set the purchase date {sale_date_str}: {str(e)}")
            logger.info("Purchase date is set to %s", sale_date_str)
        else:
            page.locator('#tgLyr_0').screenshot(path=f'{DATA_DIR}/failed-{po.id}.png')
            raise PurchaseOrderError(po,
                message=f"Purchase date {sale_date_str} is not available")
    else:
        page.locator('#tgLyr_0').screenshot(path=f'{DATA_DIR}/failed-{po.id}.png')
        logger.info("Purchase date is left default")

def __set_local_shipment(
    ordered_products: list[tuple[OrderProduct, str]]
):
    logger = _logger.getChild("__set_local_shipment")
    logger.debug("Seting local shipment")
    free_shipping_eligible_amount = reduce(
        lambda acc, op: (
            acc + (op[0].price * op[0].quantity)
            if not op[0].separate_shipping
            else 0
        ),
        ordered_products,
        0,
    )
    local_shipment = (
        free_shipping_eligible_amount
        < __config.FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD
    )
    if local_shipment:
        logger.debug("Setting combined shipment")
        __set_combined_shipping(page)
        logger.debug("Combined shipment is set")
    else:
        logger.debug("No combined shipment is needed")

def __set_combined_shipping(page: Page):
    combined_shipping = page.locator('label[for="pay-dlv_ck0_1"]')
    if combined_shipping.count() > 0:
        try_click(combined_shipping,
            lambda: page.wait_for_selector('[layer-role="close-button"]'))
        try_click(page.locator('[layer-role="close-button"]'),
            lambda: page.wait_for_selector('[layer-role="close-button"]', state='detached'))
        if not page.locator('#pay-dlv_ck0_1').is_checked():
            raise Exception("Combined shipping is not set")

def __set_receiver_name() -> None:
    logger = _logger.getChild("__set_receiver_name")
    logger.debug("Setting recipient's name")
    rcpt_name = get_receiver_name(po, 
        __config.ATOMY_RECEIVER_NAME_FORMAT)
    try_fill(page.locator("#psn-txt_0_0"), rcpt_name)
    try_click(page.locator('label[for="psn-ck_waybill"]'),
                lambda: expect(page.locator('#psn-ck_waybill')).to_be_checked(checked=True))
    logger.debug(f"Recipient's name set to {rcpt_name}")


def __set_receiver_mobile(phone="     "):
    logger = _logger.getChild("__set_receiver_mobile")
    logger.debug("Setting receiver phone number to %s", phone)
    try_fill(page.locator("#psn-txt_1_0"), phone.replace('-', ''))

def __set_receiver_address():
    logger = _logger.getChild("__set_receiver_address")
    logger.debug("Setting recipient's address")
    try:
        try_click(
            page.locator('button[data-owns="lyr_pay_addr_lst"]'),
            lambda: page.locator('#lyr_pay_addr_lst').wait_for(timeout=5000))
        address_element = find_existing_address(page, po.address)
        if address_element:
            logger.debug("Found the existing address.")
        else:
            logger.debug("No address found, creating:")
            logger.debug(po.address.to_dict())
            address_element = create_address(page, po.address, po.phone)
        if not address_element:
            raise PurchaseOrderError(po, 
                "Couldn't find or create the recipient address", screenshot=True)
        update_address(address_element, 
            name=get_receiver_name(po, 
                __config.ATOMY_RECEIVER_NAME_FORMAT),
            detailed_address=po.address.address_2,
            parent_logger=_logger)
        try_click(address_element,
                lambda: page.wait_for_selector('#btnLyrPayAddrLstClose', state='detached'))
    except PurchaseOrderError:
        raise
    except Exception as e:
        raise PurchaseOrderError(po, 
            f"Couldn't set the recipient address: {str(e)}", screenshot=True)
    
def __set_payment_params():
    logger = _logger.getChild("__set_payment_params")
    logger.debug("Setting payment parameters")
    # Set the payment method
    logger.debug("Setting payment method...")
    page.locator('#mth-tab_3').click()
    page.locator('#mth-cash-slt_0').select_option(po.company.bank_id) 
    # Set the payment mobile
    logger.debug("Setting payment mobile...")
    page.locator('#mth-cash-txt_0').fill(po.payment_phone)
    logger.debug("Payment parameters are set")

def __set_tax_info():
    logger = _logger.getChild("__set_tax_info")
    logger.info("Setting counteragent tax information")
    if po.company.tax_id != ("", "", ""):  # Company is taxable
        company = po.company
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
            try_fill(page.locator('#cash-mth-taxes-txt_0'), company.name) # Company Name
            try_fill(page.locator('#cash-mth-taxes-txt_1'), '%s%s%s' % company.tax_id) # Business Number
            try_fill(page.locator('#cash-mth-taxes-txt_2'), company.contact_person) # Representative name
            logger.debug("Find address")
            try_click(page.locator('#cash-btnAdressSearch'),
                    lambda: page.wait_for_selector('#lyr_pay_sch_bx33'))
            find_address(page, company.address.address_1)
            try_fill(page.locator('#cash-mth-taxes-txt_3_dtl'), company.address.address_2) # Detailed address
            try_fill(page.locator('#cash-mth-taxes-txt_4'), company.business_type) # Business status
            try_fill(page.locator('#cash-mth-taxes-txt_5'), company.business_category) # Business type
            try_fill(page.locator('#cash-mth-taxes-txt_6'), company.tax_phone) # Mobile
            try_fill(page.locator('#cash-mth-taxes-txt_7'), company.contact_person) # Manager
            try_fill(page.locator('#cash-mth-taxes-txt_8'), company.email) # E-mail
        logger.debug("Tax information is set")

def __submit_order() -> tuple[str, str, int]:
    '''Submits the order and returns the order details
    
    :returns tuple[str, str, int]: vendor PO ID, payment account, total price'''
    logger = _logger.getChild("__submit_order")
    logger.info("Submitting the order")
    logger.debug("Agreeing to terms")
    page.locator('label[for="fxd-agr_ck_2502000478"]').click()
    logger.debug("Submitting order")
    page.locator('button[sheet-role="pay-button"]').click()
    page.wait_for_selector('.odrComp', timeout=60000)
    vendor_po = __get_order_details(page)
    logger.debug("Created order: %s", vendor_po)
    return (
        vendor_po["vendor_po"],
        vendor_po["payment_account"],
        vendor_po["total_price"],
    )
