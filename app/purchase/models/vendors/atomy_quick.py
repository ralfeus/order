""" Fills and submits purchase order at Atomy
using quick order"""
from functools import reduce
from typing import Any, Optional
from urllib.parse import urlencode
from app.models.address import Address
from app.purchase.models.company import Company
from app.purchase.models.purchase_order import PurchaseOrder
from app.tools import get_document_from_url, get_json, invoke_curl, merge, try_perform
from datetime import datetime, timedelta
import json
import logging
from pytz import timezone
import re

from app import db
from exceptions import (
    AtomyLoginError,
    HTTPError,
    NoPurchaseOrderError,
    ProductNotAvailableError,
    PurchaseOrderError,
)
from app.orders.models.order_product import OrderProduct, OrderProductStatus
from app.purchase.models import PurchaseOrderStatus
from app.utils.atomy import atomy_login
from . import PurchaseOrderVendorBase

URL_BASE = "https://shop-api.atomy.com/svc"
URL_SUFFIX = "_siteId=kr&_deviceType=pc&locale=ko-KR"
ERROR_FOREIGN_ACCOUNT = "해외법인 소속회원은 현재 소속국가 홈페이지에서 판매중인 상품을 주문하실 수 없습니다."
ERROR_OUT_OF_STOCK = "해당 상품코드의 상품은 품절로 주문이 불가능합니다"

BANKS = {
    "32": "BUSANBANK",
    "31": "DAEGUBANK",
    "34": "GWANGJUBANK",
    "81": "HANA",
    "03": "IBK",
    "37": "JEONBUKBANK",
    "89": "KBANK",
    "04": "KOOKMIN",
    "06": "KOOKMIN",
    "39": "KYONGNAMBANK",
    "11": "NONGHYEOP",
    "71": "POST",
    "45": "SAEMAUL",
    "26": "SHINHAN",
    "88": "SHINHAN",
    "07": "SUHYEOP",
    "20": "WOORI",
}

ORDER_STATUSES = {
    "PAYMENT_INITIATED": PurchaseOrderStatus.posted,
    "PAYMENT_NOTPAID": PurchaseOrderStatus.payment_past_due,
    "SHIPMENT_DELIVERING": PurchaseOrderStatus.shipped,
    "SHIPMENT_READY": PurchaseOrderStatus.shipped,
    "SHIPMENT_COMPLETED": PurchaseOrderStatus.delivered,
    "CANCELLED": PurchaseOrderStatus.cancelled,
    "COMPLETED": PurchaseOrderStatus.delivered,
}


class AtomyQuick(PurchaseOrderVendorBase):
    """Manages purchase order at Atomy via quick order"""

    __session_cookies: list[str] = []
    __purchase_order: PurchaseOrder = None  # type: ignore
    __po_params: dict[str, dict] = {}

    def __init__(self, browser=None, logger: Optional[logging.Logger] = None, 
                 config: dict[str, Any]={}):
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
        """Posts a purchase order to Atomy based on provided data"""
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
        self.__po_params = {
            "UPDATE_ORDER_USER": {},
            "APPLY_DELIVERY_INFOS": {"payload": {"deliveryInfos": [{}]}},
            "APPLY_PAYMENT_TRANSACTION": {"payload": {"paymentTransactions": [{}]}},
        }
        self._logger.info("Logging in...")
        try:
            self.__login(purchase_order)
            self.__init_quick_order()
            self.__update_cart({"command": "CREATE_DEFAULT_DELIVERY_INFOS"})
            ordered_products, unavailable_products = self.__add_products(
                purchase_order.order_products
            )
            self.__set_purchase_date(purchase_order.purchase_date)
            # self.__set_purchase_order_id(purchase_order.id[10:]) # Receiver name
            self.__set_receiver_mobile(purchase_order.contact_phone)
            self.__set_receiver_address(
                purchase_order.address,
                purchase_order.payment_phone,
                self.__get_order_id(purchase_order),
                ordered_products,
            )
            self.__set_local_shipment(purchase_order, ordered_products)
            self.__set_payment_method()
            self.__set_payment_destination(purchase_order.bank_id)
            self.__set_payment_mobile(purchase_order.payment_phone)
            self.__set_tax_info(purchase_order)
            # self.__set_mobile_consent()
            po_params = self.__submit_order()
            self._logger.info("Created order %s", po_params[0])
            purchase_order.vendor_po_id = po_params[0]
            purchase_order.payment_account = po_params[1]
            purchase_order.total_krw = po_params[2]
            db.session.flush()
            self._set_order_products_status(
                ordered_products, OrderProductStatus.purchased
            )
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
            # Saving page for investigation
            # with open(f'order_complete-{purchase_order.id}.html', 'w') as f:
            #     f.write(self.__browser.page_source)
            self._logger.exception("Failed to post an order %s", purchase_order.id)
            raise ex

    def __update_cart(self, params: dict[str, Any]) -> bool:
        logger = self._logger.getChild("__update_cart")
        result = get_json(
            url=f"{URL_BASE}/cart/updateCart?_siteId=kr",
            headers=self.__get_session_headers(),
            raw_data="cartType=BUYNOW&salesApplication=QUICK_ORDER&channel=WEB"
            + f"&cart={self.__cart}&"
            + "&".join(
                [
                    "%s=%s" % (n, json.dumps(v) if isinstance(v, dict) else v)
                    for n, v in params.items()
                ]
            ),
        )
        return result.get("result") == "200"

    def __login(self, purchase_order):
        jwt = self.__get_token()
        stdout, stderr = invoke_curl(
            url=f"{URL_BASE}/signIn?_siteId=kr",
            headers=[{"Cookie": jwt}],
            raw_data=urlencode(
                {
                    "id": purchase_order.customer.username,
                    "password": purchase_order.customer.password,
                }
            ),
        )
        result = json.loads(stdout)
        if result["result"] == "200":
            self._logger.info(
                f"Logged in successfully as {purchase_order.customer.username}"
            )
            jwt = re.search("set-cookie: (atomySvcJWT=.*?);", stderr).group(1) #type: ignore
            self.__session_cookies = [jwt]
            return [jwt]
        else:
            raise AtomyLoginError(purchase_order.customer.username)

    def __get_session_headers(self):
        return [{"Cookie": c} for c in self.__session_cookies]

    def __get_token(self):
        _, stderr = invoke_curl(
            url="https://shop-api.atomy.com/auth/svc/jwt?_siteId=kr"
        )
        token_match = re.search("set-cookie: (atomySvcJWT=.*?);", stderr)
        if token_match is not None:
            return token_match.group(1)
        else:
            raise Exception("Could not get token. The problem is at Atomy side")

    def __init_quick_order(self):
        result = get_json(
            url=f"{URL_BASE}/cart/createCart?{URL_SUFFIX}",
            headers=self.__get_session_headers(),
            raw_data="cartType=BUYNOW&salesApplication=QUICK_ORDER&channel=WEB",
        )
        self.__cart = result["items"][0]["cartId"]

    def __send_order_post_request(self) -> str:
        """Posts order. Returns posted order ID"""
        logger = self._logger.getChild("__send_order_post_request")
        try:
            validate = get_json(
                url=f"{URL_BASE}/order/validateCheckout?{URL_SUFFIX}",
                headers=self.__get_session_headers(),
                raw_data="cartId=%s" % self.__cart,
            )
            if validate["result"] != "200":
                raise PurchaseOrderError(
                    self.__purchase_order,
                    self,
                    "The order is invalid: %s" % validate["resultMessage"],
                )

            result = try_perform(
                lambda: get_json(
                    url=f"{URL_BASE}/order/placeOrder?{URL_SUFFIX}",
                    # resolve="www.atomy.kr:443:13.209.185.92,3.39.241.190",
                    headers=self.__get_session_headers(),
                    raw_data=urlencode({"cartId": self.__cart, "customerId": ""}),
                ),
                logger=logger,
            )
            if result["result"] != "200":
                raise PurchaseOrderError(
                    self.__purchase_order, self, message=result["resultMessage"]
                )
            return result["item"]["id"]
        except HTTPError as ex:
            logger.warning(self.__po_params)
            logger.warning(ex)
            raise PurchaseOrderError(
                self.__purchase_order, self, "Unexpected error has occurred"
            )

    def __get_order_details(self, order_id) -> dict[str, Any]:
        result:dict = try_perform(
            lambda: get_json(
                url=f"{URL_BASE}/order/getOrderResult?id={order_id}&{URL_SUFFIX}",
                headers=self.__get_session_headers(),
            ),
            logger=self._logger.getChild("__get_order_details"),
        )
        return result["item"]

    def __add_products(
        self, order_products: list[OrderProduct]
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
        ordered_products: list[tuple[OrderProduct, str]] = []
        unavailable_products = {}
        for op in order_products:
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
                product, option = self.__get_product_by_id(product_id)
                if not product:
                    logger.info(
                        "Couldn't find product %s. Attempting to get it via vendor product ID",
                        product_id)
                    product_id = op.product.vendor_id
                    product, option = self.__get_product_by_vendor_id(product_id)
                    if not product:
                        raise ProductNotAvailableError(product_id)

                op.product.separate_shipping = bool(product.get('flags')
                    and "supplier" in product["flags"])
                added_product = self.__add_to_cart(product, option, op)
                if added_product["success"]:
                    ordered_products.append((op, added_product["entryId"]))
                    logger.info("Added product %s", op.product_id)
                else:
                    raise ProductNotAvailableError(
                        product_id, added_product["statusCode"]
                    )
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
        return ordered_products, unavailable_products

    def __add_to_cart(self, product, option, op):
        product_option = f',"optionProduct":"{option}"' if option is not None else ""
        res = get_json(
            url=f"{URL_BASE}/cart/addToCart?_siteId=kr",
            headers=self.__get_session_headers(),
            raw_data=(
                "cartType=BUYNOW&salesApplication=QUICK_ORDER&channel=WEB"
                + '&cart=%s&products=[{"product":"%s","quantity":%s%s}]'
            )
            % (self.__cart, product["id"], op.quantity, product_option),
        )
        return res["items"][0]

    def __get_product_by_id(self, product_id):
        try:
            result = get_json(
                url=f"{URL_BASE}/atms/search?{URL_SUFFIX}",
                # resolve="www.atomy.kr:443:13.209.185.92,3.39.241.190",
                headers=self.__get_session_headers(),
                raw_data=f"searchKeyword={product_id}&page=1&from=0&pageCount=0&pageSize=20&size=20&isQuickSearch=true",
            )
            if result["totalCount"] > 0:
                products = [items for items in result['items'] 
                            if items['materialCode'] == product_id]
                product = products[0] if len(products) == 1 \
                    else sorted(result["items"], key=lambda i: i['materialCode'])[0]
                option = (
                    self.__get_product_option(product, product_id)
                    if product["optionType"]["value"] == "mix"
                    else None
                )
                return product, option
        except HTTPError:
            self._logger.warning(
                "Product %s: Couldn't get response from Atomy server in several attempts. Giving up",
                product_id,
            )
        return None, None
    
    def __get_product_by_vendor_id(self, vendor_product_id):
        logger = self._logger.getChild('__get_product_by_vendor_id()')
        try:
            result = get_json(
                url=f'{URL_BASE}/product/simpleList?productIds={vendor_product_id}&_siteId=kr&_deviceType=pc',
                headers=self.__get_session_headers()
            )
            if not isinstance(result, dict) or len(result['items']) == 0:
                return None, None
            return result['items'][0], None
        except Exception as e:
            logger.warning("Couldn't get product %s: %s", vendor_product_id, e)
        return None, None

    def __get_product_option(self, product, option_id):
        result = get_json(
            url=f"{URL_BASE}/product/options?productId={product['id']}&_siteId=kr"
            + "&_deviceType=pc&locale=en-KR",
            headers=self.__get_session_headers(),
        )
        return [
            o
            for o in result["item"]["option"]["productOptions"]
            if o["materialCode"] == option_id
        ][0]["optionProduct"]["value"]

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

    def __set_purchase_date(self, purchase_date):
        logger = self._logger.getChild("__set_purchase_date")
        if purchase_date and self.__is_purchase_date_valid(purchase_date):
            sale_date = purchase_date
        else:
            sale_date = datetime.now()
        if sale_date.weekday() == 6 or (sale_date.month, sale_date.day) == (1, 1):
            sale_date += timedelta(days=1)
        merge(
            self.__po_params["UPDATE_ORDER_USER"],
            {"payload": {"salesDate": sale_date.strftime("%Y-%m-%d")}},
        )

    def __set_local_shipment(
        self, purchase_order, ordered_products: list[tuple[OrderProduct, str]]
    ):
        logger = self._logger.getChild("__set_local_shipment")
        logger.debug("Set local shipment")
        free_shipping_eligible_amount = reduce(
            lambda acc, op: acc + (op[0].price * op[0].quantity)
            if not op[0].product.separate_shipping
            else 0,
            ordered_products,
            0,
        )
        local_shipment = (
            free_shipping_eligible_amount
            < self.__config["FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD"]
        )
        if local_shipment:
            logger.debug("Setting combined shipment params")
            if self.__update_cart({
                    "command": "UPDATE_ASSORTED_PACKING",
                    "payload": {
                        "id": self.__get_delivery_info(),
                        "assortedPacking": True,
                    },
                }):
                logger.debug("Successfully set combined shipping")
            else:
                logger.warning("Couldn't set combined shipping")
        else:
            logger.debug("No combined shipment is needed")

    def __get_delivery_info(self):
        res = get_json(
            url=f"{URL_BASE}/cart/getBuynowCart"
            + f"?cartType=BUYNOW&salesApplication=QUICK_ORDER&cart={self.__cart}"
            + "&options=%5B%22PROMOTION%22%2C%22SALES_RULE%22%2C%22ENTRIES%22%2C%22PAYMENT_TYPE%22%2C%22DELIVERY_INFOS%22%5D&channel=WEB&_siteId=kr&_deviceType=pc"
            + "&locale=en-KR",
            headers=self.__get_session_headers(),
        )
        return res["item"]["deliveryInfos"][0]["id"]
    
    def __get_order_id(self, purchase_order: PurchaseOrder) -> str:
        order_id_parts = purchase_order.id[8:].split('-')
        return order_id_parts[2][1:] + "ㅡ" + order_id_parts[1] + "ㅡ" + order_id_parts[0]
        # return purchase_order.id[8:].replace("-", "ㅡ")

    def __set_purchase_order_id(self, purchase_order_id):
        logger = self._logger.getChild("__set_purchase_order_id")
        logger.info("Setting purchase order ID")
        adapted_po_id = purchase_order_id.replace("-", "ㅡ")
        logger.debug(self.__po_params["UPDATE_ORDER_USER"])

        merge(
            self.__po_params["UPDATE_ORDER_USER"],
            {"payload": {"userName": adapted_po_id}},
        )

    def __set_receiver_mobile(self, phone="     "):
        logger = self._logger.getChild("__set_receiver_mobile")
        logger.debug("Setting receiver phone number")
        merge(
            self.__po_params["UPDATE_ORDER_USER"],
            {"payload": {"userCellphone": phone.replace("-", "")}},
        )
        merge(
            self.__po_params["APPLY_DELIVERY_INFOS"]["payload"]["deliveryInfos"][0],
            {"address": {"cellphone": phone.replace("-", "")}},
        )

    def __set_payment_mobile(self, phone="010-6275-2045"):
        logger = self._logger.getChild("__set_payment_mobile")
        logger.debug("Setting phone number for payment notification")
        if phone != "":
            self.__po_params["APPLY_PAYMENT_TRANSACTION"]["payload"][
                "paymentTransactions"
            ][0]["phoneNumber"] = phone.replace("-", "")
            self.__po_params["APPLY_PAYMENT_TRANSACTION"]["payload"][
                "paymentTransactions"
            ][0]["taxInvoice"] = {"number": phone.replace("-", "")}
        else:
            self._logger.info("Payment phone isn't provided")

    def __get_addresses(self) -> list[dict[str, str]]:
        result = get_json(
            url=f"{URL_BASE}/address/getDeliveryAddressList?{URL_SUFFIX}",
            headers=self.__get_session_headers(),
        )
        return result.get("items") or []

    def __create_address(self, address: Address, phone, order_id):
        result = get_json(
            url=f"{URL_BASE}/address/createAddress?_siteId=kr&_deviceType=pc&locale=en-GB",
            headers=self.__get_session_headers(),
            method="POST",
            raw_data="address="
            + json.dumps({
                "zipCode": address.zip,
                "address": address.address_1,
                "state": "",
                "city": "",
                "type": "SHIPPING",
                "name": order_id,
                "cellphone": phone.replace("-", ""),
                "telephone": "",
                "detailAddress": address.address_2,
                "fullAddress": address.address_1 + " " + address.address_2,
                "message": "",
                "defaultAddress": True,
                "favorites": False,
            }),
        )
        return result["item"]
    
    def __update_address(self, atomy_address: dict, address: Address, phone, order_id: str) -> dict:
        result = get_json(
            url=f"{URL_BASE}/address/updateAddress?{URL_SUFFIX}",
            headers=self.__get_session_headers(),
            method="POST",
            raw_data="address=" + json.dumps(merge(
                atomy_address, 
                {
                    "address": address.address_1,
                    "cellphone": phone,
                    "detailAddress": address.address_2,
                    "fullAddress": f"{address.address_1} {address.address_2}",
                    "name": order_id,
                    "zipCode": address.zip,
                    "type": atomy_address['type']['value'],
                }, force=True)
            )
        )
        if result['result'] != '200':
            raise result['resultMessage']
        return result['item']

    def __set_receiver_address(
        self,
        address: Address,
        phone,
        order_id,
        ordered_products: list[tuple[OrderProduct, str]],
    ):
        logger = self._logger.getChild("__set_receiver_address")
        logger.debug("Setting shipment address")
        addresses = [a for a in self.__get_addresses() if a["defaultAddress"]]
        atomy_address = (
            self.__update_address(addresses[0], address, phone, order_id) 
                if len(addresses) > 0
                else self.__create_address(address, phone, order_id)
        )
        merge(
            self.__po_params["APPLY_DELIVERY_INFOS"]["payload"]["deliveryInfos"][0],
            {
                "sequence": 0,
                "address": atomy_address,
                "deliveryMode": "DELIVERY_KR",
                "entries": [
                    {
                        "entryNumber": i,
                        "cartEntry": ordered_products[i][1],
                        "quantity": ordered_products[i][0].quantity,
                    }
                    for i in range(len(ordered_products))
                ],
            },
            force=True,
        )
        if self.__update_cart(
            {
                "command": "APPLY_DELIVERY_INFOS",
                **self.__po_params["APPLY_DELIVERY_INFOS"],
            }
        ):
            logger.debug("Successfully set address")
        else:
            raise PurchaseOrderError(
                self.__purchase_order, self, "Couldn't set address"
            )

    def __set_payment_method(self):
        logger = self._logger.getChild("__set_payment_method")
        logger.debug("Setting payment method")
        if self.__update_cart(
            {"command": "UPDATE_PAYMENT_TYPE", "payload": {"id": "ACCOUNT_TRANSFER"}}
        ):
            logger.debug("Payment method was successfully set")
        else:
            raise PurchaseOrderError(
                self.__purchase_order, self, "Couldn't set payment method"
            )

    def __set_payment_destination(self, bank_id):
        logger = self._logger.getChild("__set_payment_destination")
        logger.debug("Setting payment receiver")
        payment_config, amount, deadline = self.__get_payment_params()
        merge(
            self.__po_params["APPLY_PAYMENT_TRANSACTION"]["payload"][
                "paymentTransactions"
            ][0],
            {
                "plannedAmount": amount,
                "depositDeadline": deadline,
                "status": "AUTHORIZATION",
                "info": {"bank": BANKS[bank_id], "config": payment_config["id"]},
            },
        )

    def __get_payment_params(self) -> tuple[dict[str, Any], str, str]:
        result = get_json(
            url=f"{URL_BASE}/cart/getBuynowCart"
            + f"?cartType=BUYNOW&salesApplication=QUICK_ORDER&cart={self.__cart}"
            + "&options=%5B%22PROMOTION%22%2C%22SALES_RULE%22%2C%22ENTRIES%22%2C%22PAYMENT_TYPE%22%2C%22DELIVERY_INFOS%22%5D&channel=WEB&_siteId=kr"
            + "&_deviceType=pc&locale=en-KR",
            headers=self.__get_session_headers(),
        )
        deadline = self.__get_payment_deadline(
            result["item"]["paymentType"]["configs"][0]["id"]
        )
        return (
            result["item"]["paymentType"]["configs"][0],
            result["item"]["totalPrice"],
            deadline,
        )

    def __get_payment_deadline(self, payment_config_id):
        result = get_json(
            url=f"{URL_BASE}/payment/getDepositDeadline"
            + f"?paymentTypeConfig={payment_config_id}&_siteId=kr"
            + "&_deviceType=pc&locale=en-KR",
            headers=self.__get_session_headers(),
        )
        d = result["item"]["deadline"]
        return d[:4] + d[5:7] + d[8:10] + d[11:13] + d[14:16] + d[17:19]

    def __set_tax_info(self, purchase_order: PurchaseOrder):
        self._logger.debug("Setting counteragent tax information")
        if purchase_order.company.tax_id != ("", "", ""):  # Company is taxable
            if purchase_order.company.tax_simplified:
                merge(
                    self.__po_params["APPLY_PAYMENT_TRANSACTION"]["payload"][
                        "paymentTransactions"
                    ][0],
                    {
                        "taxInvoice": {
                            "type": "CASH",
                            "proofType": "PROOF",
                            "numberType": "BRN",
                            "number": "%s%s%s" % purchase_order.company.tax_id,
                        }
                    },
                    force=True,
                )
            else:
                atomy_company_id, is_new = self.__get_atomy_company(
                    purchase_order.customer.username, purchase_order.company.tax_id
                )
                if atomy_company_id is None:
                    atomy_company_id, is_new = self.__create_atomy_company(
                        purchase_order.company
                    )
                merge(
                    self.__po_params["APPLY_PAYMENT_TRANSACTION"]["payload"][
                        "paymentTransactions"
                    ][0],
                    {
                        "taxInvoice": {
                            "type": "TAX",
                            "proofType": "PROOF",
                            "numberType": "BRN",
                            "number": "%s%s%s" % purchase_order.company.tax_id,
                            "businessLicense": atomy_company_id,
                            "newBusinessNumber": is_new,
                            "isNonCustomer": True,
                        }
                    },
                    force=True,
                )
        else:
            merge(
                self.__po_params["APPLY_PAYMENT_TRANSACTION"]["payload"][
                    "paymentTransactions"
                ][0],
                {
                    "taxInvoice": {
                        "type": "NONE",
                        "proofType": "DEDUCTION",
                        "numberType": "CPN",
                    }
                },
            )

    def __get_atomy_company(self, username, tax_id) -> tuple[Any, bool]:
        logger = self._logger.getChild("__get_atomy_company")
        result = get_json(
            url=f"{URL_BASE}/businessTaxbill/getBusinessTaxbillList?customer={username}&{URL_SUFFIX}",
            headers=self.__get_session_headers(),
        )
        logger.debug(result)
        company = [
            company
            for company in result.get("items")  # type: ignore
            if company["businessNumber"] == "%s%s%s" % tax_id
        ]
        return (company[0]["id"], False) if len(company) > 0 else (None, False)

    def __create_atomy_company(self, company: Company):
        logger = self._logger.getChild("__create_atomy_company")
        logger.info("Creating new company object")
        payload = {
                    "companyName": company.name,
                    "businessNumber": "%s%s%s" % company.tax_id,
                    "ceoName": company.contact_person,
                    "address": company.address.address_1,
                    "addressDetail": company.tax_address.address_2,
                    "zipCode": company.tax_address.zip,
                    "industry": company.business_category,
                    "category": company.business_type,
                    "mobileNumber": company.tax_phone,
                    "contactName": company.contact_person,
                    "email": company.email,
                    "isNew": "true",
                    "saveAsCustomer": "false",
                    "isNonCustomer": "true",
                }
        logger.debug(payload)
        try:
            result = get_json(
                url=f"{URL_BASE}/businessTaxbill/createBusinessTaxbill?{URL_SUFFIX}",
                headers=self.__get_session_headers(),
                raw_data=urlencode(
                    payload
                ),
            )
            logger.debug(result)
            return result["item"]["id"], True
        except Exception as e:
            logger.warning(e)
            raise PurchaseOrderError(self.__purchase_order, self, 
                                     result.get('resultMessage'))

    def __submit_order(self):
        def update_cart_part(command):
            if not self.__update_cart(
                {"command": command, **self.__po_params[command]}
            ):
                raise PurchaseOrderError(
                    self.__purchase_order, self, f"Couldn't update cart part: {command}"
                )

        logger = self._logger.getChild("__submit_order")
        logger.info("Submitting the order")
        logger.debug("Setting order params")
        logger.debug(self.__po_params)
        update_cart_part("UPDATE_ORDER_USER")
        update_cart_part("APPLY_PAYMENT_TRANSACTION")
        order_id = self.__send_order_post_request()
        vendor_po = self.__get_order_details(order_id=order_id)
        logger.debug("Created order: %s", vendor_po)
        return (
            order_id,
            vendor_po["paymentTransactions"][0]["info"]["accountNumber"],
            vendor_po["totalPrice"],
        )

    def update_purchase_order_status(self, purchase_order):
        logger = self._logger.getChild("update_purchase_order_status")
        logger.info("Updating %s status", purchase_order.id)
        logger.debug("Logging in as %s", purchase_order.customer.username)
        self.__login(purchase_order)
        logger.debug("Getting POs from Atomy...")
        vendor_purchase_orders = self.__get_purchase_orders()
        self._logger.debug("Got %s POs", len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            # logger.debug(str(o))
            if o["id"] == purchase_order.vendor_po_id:
                purchase_order.set_status(ORDER_STATUSES[o["orderStatus"]["value"]])
                return purchase_order

        raise NoPurchaseOrderError(
            "No corresponding purchase order for Atomy PO <%s> was found" % 
            purchase_order.vendor_po_id
        )

    def update_purchase_orders_status(self, subcustomer, purchase_orders):
        logger = self._logger.getChild("update_purchase_orders_status")
        logger.info("Updating %s POs status", len(purchase_orders))
        logger.debug("Attempting to log in as %s...", subcustomer.name)
        self.__login(purchase_orders[0])
        logger.debug("Getting subcustomer's POs")
        vendor_purchase_orders = self.__get_purchase_orders()
        logger.debug("Got %s POs", len(vendor_purchase_orders))
        for o in vendor_purchase_orders:
            # logger.debug(str(o))
            if ORDER_STATUSES[o["orderStatus"]["value"]] == PurchaseOrderStatus.posted:
                logger.debug("Skipping PO %s", o["id"])
                continue
            filtered_po = [
                po for po in purchase_orders if po and po.vendor_po_id == o["id"]
            ]
            try:
                filtered_po[0].set_status(ORDER_STATUSES[o["orderStatus"]["value"]])
            except IndexError:
                logger.warning(
                    "No corresponding purchase order for Atomy PO <%s> was found",
                    o["id"],
                )

    def __get_purchase_orders(self):
        logger = self._logger.getChild("__get_purchase_orders")
        logger.debug("Getting purchase orders")
        res = get_json(
            url=f"{URL_BASE}/order/getOrderList?"
            + "period=MONTH&orderStatus=&salesApplication=&page=1&pageSize=100"
            + f"&fromDate=&toDate=&{URL_SUFFIX}",
            headers=self.__get_session_headers(),
        )

        if res["result"] == "200":
            return res["items"]
        else:
            raise PurchaseOrderError()
