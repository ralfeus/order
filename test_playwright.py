import json
import re
from time import sleep
from playwright.sync_api import Locator, expect, sync_playwright

def try_click(object: Locator, execute_criteria, retries=3):
    exception = Exception(f"Failed to click the object after {retries} retries.")
    for _ in range(retries):
        try:
            object.click(timeout=5000)
            execute_criteria()
            sleep(.7)
            return
        except Exception as e:
            print(f"Retrying click on {object}: {e}")
            exception = e
    raise exception

def fill(object: Locator, data: str):
    object.fill(data)
    expect(object).to_have_value(data)

def find_address(base_address: str):
    page.locator('#lyr_pay_sch_bx33').fill(base_address)  # Base address
    page.locator('button[address-role="search-button"]').click()
    page.locator('button[address-role="select-button"]').click()

URL_BASE = "https://kr.atomy.com"
product_id = '003632'
with sync_playwright() as p:
        # browser = p.chromium.launch(headless=True) 
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.new_page()
        page.set_viewport_size({"width": 1420, "height": 1080})
        # Login
        print("Logging in...")
        page.goto(f"{URL_BASE}/login")
        page.fill("#login_id", '23426444')
        page.fill("#login_pw", 'atomy#01')
        page.click(".login_btn button")
        page.wait_for_load_state()

        # Quick Order
        print("Navigating to Quick Order...")
        try:
            print('Changing language')
            page.evaluate('overpass.util.setLanguage("en");')
            page.wait_for_load_state("networkidle")
            try:
                page.click('button[layer-role="close-button"]', timeout=2000)
            except Exception as e:
                pass  # No popup to close
            print('Opening Quick Order')
            page.click('a[href^="javascript:overpass.cart.regist"]')
            page.wait_for_load_state()
        except Exception as e:
            page.screenshot(path="quick_order.png")
            print(f"Failed to open an order form: {e}. Exiting.")
            exit(1)
        # Open product add
        print("Adding items to cart...")
        for _ in range(3):
            try:
                page.click('button[quick-form-button="search"]')
                page.wait_for_selector('#schInput', timeout=5000)
                break
            except Exception as e:
                print(f"Retrying click")
        # Search for product
        page.fill('#schInput', product_id)
        try_click(page.locator('#schBtn'),
              lambda: page.wait_for_selector('#lyr_common_loading_dim', state='detached'))
        try:
            button = page.locator('button[cart-role="btn-solo"]')
            if button.count() > 0:
                try_click(button, lambda: page.wait_for_selector(f'[goods-cart-role="{product_id}"]'))
                page.locator(f'[goods-cart-role="{product_id}"] #selected-qty1').fill('2')
            else:
                # It might be a product's option
                try_click(page.locator('button[option-role="opt-layer-btn"]'),
                          lambda: page.wait_for_selector('#gds_opt_0'))
                base_product_id = page.locator('.lyr-gd__num').text_content()
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
                option = [o for o in list(result.values()) if o['materialCode'] == product_id][0]
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
                product_loc.locator('input#selected-qty1').fill('2')

        except Exception as e:
            page.screenshot(path="quick_order.png")
            print(f"Failed to add product: {e}. Exiting.")
            exit(1)

        print("Check restrictions")
        result = page.evaluate(f"""
            async () => {{
                const res = await fetch('{URL_BASE}/cart/checkPurchaseRestrirction', {{
                    method: 'POST',
                    headers: {{'content-type': 'application/json'}},
                    body: '{{"goodsNoNmList":{{"000121":""}}}}'
                }});
                return await res.json()
            }}
        """)        
        print("Creating a cart")
        page.locator('[cart-role="quick-cart-send"]').click()
        try_click(
            page.locator('[layer-role="close-button"]'),
            lambda: page.wait_for_selector('#schInput', state='detached'))
        # Set the sale date
        print("Setting sale date...")
        try_click(page.locator('ul.slt-date input[value="2025-08-08"] + label'),
                  lambda: expect(page.locator(
                      'ul.slt-date input[value="2025-08-08"]'))
                      .to_be_checked())
        # Set the name
        print("Setting recipient's name...")
        page.locator("#psn-txt_0_0").fill("Test User")
        expect(page.locator("#psn-txt_0_0")).to_have_value("Test User")
        # Set the phone number
        print("Setting phone number...")
        page.locator("#psn-txt_1_0").fill("01050062045")
        expect(page.locator("#psn-txt_1_0")).to_have_value("01050062045")
        # Set the address
        print("Setting address...")
        for _ in range(3):
            try:
                page.locator('button[data-owns="lyr_pay_addr_lst"]').click()
                page.locator('#btnOrderDlvpReg').wait_for(timeout=5000)
                break
            except Exception as e:
                print(f"Retrying click")
        addresses = page.locator('#dlvp_list > dl.lyr-address')
        if addresses.count() > 0:
            print(f"Found {addresses.count()} addresses.")
        else:
            print("No addresses found, creating a new one.")
            page.locator('#btnOrderDlvpReg').click()
            page.wait_for_selector('div.lyr-pay_addr_add')
            fill(page.locator('#dlvpNm'), 'Test-User')
            fill(page.locator('#cellNo'), '01050062045')
            try_click(page.locator('#btnAdressSearch'), 
                lambda: page.wait_for_selector('#lyr_pay_sch_bx33', timeout=5000))
            fill(page.locator('#lyr_pay_sch_bx33'), '서울특별시 중구 다산로36길 110(신당동, 신당푸르지오)')  # Example base address
            page.locator('button[address-role="search-button"]').click()
            page.locator('button[address-role="select-button"]').click()
            fill(page.locator('#dtlAddr'), '108동1904호')
            page.locator('#dtlAddr').dispatch_event('keyup')
            page.locator('label[for="baseYn"]').click()
            page.locator('#btnSubmit').click()
            page.wait_for_selector('div.lyr-pay_addr_add', state='detached')
        try_click(page.locator('#dlvp_list > dl.lyr-address').first,
                  lambda: page.wait_for_selector('#btnLyrPayAddrLstClose', state='detached'))
        # Set the combined shipping
        print("Set combined shipping")
        combined_shipping = page.locator('label[for="pay-dlv_ck0_1"]')
        if combined_shipping.count() > 0:
            try_click(combined_shipping,
                lambda: page.wait_for_selector('[layer-role="close-button"]'))
            try_click(page.locator('[layer-role="close-button"]'),
                lambda: page.wait_for_selector('[layer-role="close-button"]', state='detached'))
        
        # Set the payment method
        print("Setting payment method...")
        page.locator('#mth-tab_3').click()
        page.locator('#mth-cash-slt_0').select_option('06') 
        # Set the payment mobile
        print("Setting payment mobile...")
        page.locator('#mth-cash-txt_0').fill('01050062045')
        # Set the tax information
        print("Setting tax information...")
        page.locator('label[for="cash-mth-proof_rdo_1"]').click()
        page.locator('label[for="pay_important_ck_0"]').click()
        confirm_button = page.locator('button[layer-role="confirm-button"]')
        expect(confirm_button).to_be_enabled()
        confirm_button.click()
        print('Set usage purpose')
        page.locator('#cash-mth-proof-slt_0').select_option('cash-receipt_1')
        page.locator('#cash-mth-receipt_opr').fill('01012345678')
        page.locator('label[for="cash-mth-cash-btm_ck0"]').click()
        # confirm_button = page.locator('button[layer-role="confirm-button"]')
        # print("Switch to Tax Invoice")
        # try_click(page.locator('label[for="cash-mth-proof_rdo_2"]'),
        #           lambda: expect(confirm_button).to_be_attached())
        # print("Close notice")
        # try_click(page.locator('label[for="pay_important_ck_1"]'),
        #           lambda: expect(confirm_button).to_be_enabled())
        # try_click(confirm_button,
        #           lambda: expect(confirm_button).not_to_be_attached())
        # print("Select New")
        # try_click(page.locator('label[for="cash-mth-taxes_rdo_1"]'),
        #           lambda: page.wait_for_selector('#cash-mth-taxes-txt_0'))
        # print("Fill data")
        # fill(page.locator('#cash-mth-taxes-txt_0'), 'Test') # Company Name
        # fill(page.locator('#cash-mth-taxes-txt_1'), '4181411817') # Business Number
        # fill(page.locator('#cash-mth-taxes-txt_2'), 'Test') # Representative name
        # try_click(page.locator('#cash-btnAdressSearch'),
        #           lambda: page.wait_for_selector('#lyr_pay_sch_bx33'))
        # find_address('서울특별시 금천구 두산로 70 (독산동)')
        # fill(page.locator('#cash-mth-taxes-txt_3_dtl'), 'Test') # Detailed address
        # fill(page.locator('#cash-mth-taxes-txt_4'), 'Test status') # Business status
        # fill(page.locator('#cash-mth-taxes-txt_5'), 'Test status') # Business type
        # fill(page.locator('#cash-mth-taxes-txt_6'), '01023456789') # Mobile
        # fill(page.locator('#cash-mth-taxes-txt_7'), 'Test mgr') # Manager
        # fill(page.locator('#cash-mth-taxes-txt_8'), 'test@mail.com') # E-mail

        # Agree to terms and submit
        print("Agreeing to terms")
        page.locator('label[for="fxd-agr_ck_2502000478"]').click()
        print("Submitting order")
        page.locator('button[sheet-role="pay-button"]').click()

        page.wait_for_load_state('networkidle')
        ord_data = [ m.string 
            for m in [
                re.search(r"JSON.parse\((.*)\)", s.text_content() or '')
                for s in page.locator('script').all()
            ] if m != None
        ][0]
        po_num = re.search(r"saleNum.*?(\d+)", ord_data).group(1)
        acc_num = re.search(r"ipgumAccountNo.*?(\d+)", ord_data).group(1)
        sleep(2)
        page.screenshot(path="quick_order.png")
        browser.close()
