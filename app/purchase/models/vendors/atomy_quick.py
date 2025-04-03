"""Fills and submits purchase order at Atomy
using quick order"""

from functools import reduce
from typing import Any, Optional
from urllib.parse import urlencode

from app.models.address import Address
from app.purchase.models.company import Company
from app.purchase.models.purchase_order import PurchaseOrder
from app.tools import get_html, get_json, invoke_curl, try_perform
from utils.atomy import atomy_login2
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
from . import PurchaseOrderVendorBase

URL_BASE = "https://kr.atomy.com"
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

class AtomyQuick(PurchaseOrderVendorBase):
    """Manages purchase order at Atomy via quick order"""

    __session_cookies: list[str] = []
    __purchase_order: PurchaseOrder = None  # type: ignore

    def __init_payload(self):
        self.__mst = {
            "seq": 5,
            "clientNo": "ATOMY",
            "siteNo": "KR",
            "jisaCode": "01",
            "saleDate": None,  # Set by `__set_purchase_date`
            "buPlace": "7000",
            "ordererNm": None,  # Set by `__set_receiver_address`
            "cellNo": None,  # To be set by `__set_receiver_mobile`
            "deliMethodCd": "3",
            "deliCostDiviCd": "1",
            "ordChnlCd": "10",
            "ordChnlCdTemp": "10",
            "cartGrpCd": "10",
            "packingNo": None,
            "packingYn": "N",
            "mailRecvYn": "N",
            "ordKindCd": "03",
            "nomemOrdYn": "N",
            "senderPrintYn": "Y",
            "smsRecvYn": "Y",
            "cashReceiptUseDiviCd": "1",  # TODO: Check if used for tax id
            "cashReceiptIssueCd": "1",  # TODO: Check if used for tax id
            "cashReceiptCertNo": "010-000-1234",  # Most likely to be set in `__set_tax_info`
            "saleNo": None,  # To set provided from `mersList`
        }
        self.__dlvpList = [
            {
                "count": 0,
                "deliFormCd": "10",
                "mbrDlvpSeq": "0000001",
                "dlvpDiviCd": "10",
                "baseYn": "Y",
                "dlvpNm": None,  # Set by `__set_order_id`
                "recvrPostNo": None,  # Postal code is to be set by `__set_receiver_address`
                "recvrBaseAddr": None,  # To be set by `__set_receiver_address`
                "recvrDtlAddr": None,  # To be set by `__set_receiver_address`
                "cellNo": None,  # To be set by `__set_receiver_mobile`
                "publicPlace": False,
                "express": False,
                "seq": 0,
                "dlvpNo": "1",
                "recvrNm": None,  # Set by `__set_receiver_address`
                "buPlace": "",
                "deliTypeCd": "3",
                "packingMemo": None,
                "deliCostTaxRate": 0,
                "weekDeliveryPossYn": "N",
                "saleAmtDispYn": "Y",
            }
        ]
        self.__goodsList = [  ] # Propagated in `__add_products`
        self.__beneList = [
            {
                "seq": 1,
                "tempOrdSeq": "1",
                "issueDiviCd": "10",
                "costKindCd": "20",
                "costKindDtlCd": "2010",
                "relDiviCd": "10",
                "deliCostAmt": 0,
                "deliCostPoliNo": "KR00011",
                "stAmt": 50000,
                "costAmt": 0,
                "taxAmt": 0,
                "deliCostDiviCd": "0",
                "oriDeliCostAmt": 0,
                "deliTaxVal": "1.1",
                "deliTaxTypeCd": "15",
            }
        ]
        self.__po_params: dict[str, Any] = {
            "maxSeq": 6,
            "mst": self.__mst,
            "payList": [
                {
                    "seq": 4,
                    "payMean": "vbank",
                    "mersDiviCd": "101",
                    "payMeanCd": "1401",
                    "payAmt": None,  # Set by `__set_payment_params`
                    "payVat": None,  # Set by `__set_payment_params`
                    "bankCd": None,  # Set by `__set_payment_params`
                    "payerPhone": None,  # Set by `__set_payment_params`
                    "cashReceiptType": "DEDUCTION",  # TODO: Depends on tax method?
                    "registrationNumber": "0100001234",  # Set by `__set_tax_info`
                    "payNo": None,  # To be obtained from `mersList`
                    "vanData": {
                        "data": {
                            "bankCd": None,  # Set by `__set_payment_params`
                            "dispGoodsNm": None,  # Set by `__set_payment_params`
                            "ordererNm": None,  # Set by `__set_payment_params`
                            "expiry": None,  # `__get_payment_deadline`
                            "cashReceiptType": "DEDUCTION",  # TODO: Depends on tax method?
                            "registrationNumber": "0100001234",  # Set by `__set_tax_info`
                        },
                        "vanCd": "50",
                        "saleNo": None,  # To be obtained from `mersList`
                        "payNo": None,  # To be obtained from `mersList`
                        "payMeanCd": "1401",
                        "payMean": "vbank",
                        "mersDiviCd": "101",
                        "payAmt": None,  # Set by `__set_payment_params`
                        "timezone": "Asia/Seoul",
                        "paySiteNo": "KR",
                        "payJisaCode": "01",
                        "payClientNo": "ATOMY",
                        "payChnlCd": "10",
                    },
                    "webhook": False,
                }
            ],
            "dlvpList": self.__dlvpList,
            "goodsList": self.__goodsList,  # To be set by `__add_products`
            "beneList": self.__beneList,
            "saveYn": "N",
        }
        self.__payment_payload: dict[str, Any] = {
            "ordData": {
                "maxSeq": 6,
                "mst": self.__mst,
                "payList": [
                    {
                        "mersDiviCd": "101",
                        "bankCd": None,  # Set in `__set_payment_params`
                        "expiry": None,  # Set in `__get_payment_deadline`
                    }
                ],
                "dlvpList": self.__dlvpList,
                "goodsList": self.__goodsList,
                "beneList": self.__beneList,
                "saveYn": "N",
            },
            "payData": {
                "entry": {
                    "paySiteNo": "KR",
                    "payJisaCode": "01",
                    "payClientNo": "ATOMY",
                    "payChnlCd": "10",
                    "origin": "https://kr.atomy.com",
                },
                "payLocale": {
                    "payCountry": "KR",
                    "timezone": "Asia/Seoul",
                    "payLanguage": "ko",
                    "currency": {"name": "KRW", "code": "410"},
                },
                "returnUrl": "https://kr.atomy.com/order/regist",
                "completeUrl": "https://kr.atomy.com/order/finish",
            },
        }

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
        self._logger.info("Logging in...")
        try:
            self.__login(purchase_order)
            self.__init_quick_order()
            ordered_products, unavailable_products = self.__add_products(
                purchase_order.order_products
            )
            self.__set_purchase_date(purchase_order.purchase_date)
            self.__set_receiver_mobile(purchase_order.contact_phone)
            self.__set_receiver_address(
                purchase_order.address,
                purchase_order.payment_phone,
                self.__get_order_id(purchase_order),
            )
            self.__set_local_shipment(purchase_order, ordered_products)
            self.__set_payment_params(purchase_order, ordered_products)
            self.__set_tax_info(purchase_order)
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
            self._logger.exception("Failed to post an order %s", purchase_order.id)
            raise ex

    def __login(self, purchase_order):
        # _, stderr = invoke_curl(
        #     url=f"{URL_BASE}/login/doLogin",
        #     headers=[{"content-type": "application/json"}],
        #     raw_data=json.dumps(
        #         {
        #             "mbrLoginId": purchase_order.customer.username,
        #             "pwd": purchase_order.customer.password,
        #             "saveId": False,
        #             "autoLogin": False,
        #             "recaptcha": "",
        #         }
        #     ),
        # )
        # if re.search("HTTP.*200", stderr) is not None:
        #     self._logger.info(
        #         f"Logged in successfully as {purchase_order.customer.username}"
        #     )
        #     # It's confirmed JSESSIONID is sufficient
        #     jwt = re.search("set-cookie: (JSESSIONID=.*?);", stderr).group(1)  # type: ignore
        #     self.__session_cookies = [jwt]
        #     return [jwt]
        # else:
        #     raise AtomyLoginError(purchase_order.customer.username)
        self.__session_cookies = [atomy_login2(
            purchase_order.customer.username, purchase_order.customer.password)]
        return self.__session_cookies

    def __get_session_headers(self):
        return [{"Cookie": c} for c in self.__session_cookies]

    def __init_quick_order(self):
        '''Initializes the quick order. Doesn't return anything but essential
        for order creation'''
        self.__init_payload()
        get_json(
            url=f"{URL_BASE}/cart/registCart/30",
            headers=self.__get_session_headers(),
            raw_data="[]",
        )

    def __send_payment_request(self) -> tuple[str, str]:
        logger = self._logger.getChild("__send_payment_request")
        logger.info("Sending payment request")
        logger.debug("Payment payload")
        logger.debug(json.dumps(self.__payment_payload))
        result = get_json(
            url=f"{URL_BASE}/overpass-payments/support/mersList",
            headers=self.__get_session_headers(),
            raw_data=json.dumps(self.__payment_payload)
        )
        return result['mersList'][0]['payNo'], result['mersList'][0]['saleNo']

    def __send_order_post_request(self, pay_no, sale_no) -> str:
        """Posts order. Returns posted order ID"""
        logger = self._logger.getChild("__send_order_post_request")
        self.__mst["saleNo"] = sale_no
        self.__po_params['payList'][0]['payNo'] = pay_no
        self.__po_params['payList'][0]['vanData']['payNo'] = pay_no
        self.__po_params['payList'][0]['vanData']['saleNo'] = sale_no
        logger.debug("Order params")
        logger.debug(json.dumps(self.__po_params))
        try:
            stdout, stderr = try_perform(
                lambda: invoke_curl(
                    url=f"{URL_BASE}/order/regist",
                    # resolve="www.atomy.kr:443:13.209.185.92,3.39.241.190",
                    headers=self.__get_session_headers() + [
                        {"content-type": "application/json; charset=UTF-8"}],
                    raw_data=json.dumps(self.__po_params),
                ),
                logger=logger,
            )
            if re.search("HTTP.*200", stderr) is None:
                raise PurchaseOrderError(
                    self.__purchase_order, self, message=stdout
                )

        except HTTPError as ex:
            logger.warning(self.__po_params)
            logger.warning(ex)
            raise PurchaseOrderError(
                self.__purchase_order, self, "Unexpected error has occurred"
            )

    def __get_order_details(self) -> dict[str, Any]:
        stdout, stderr = try_perform(
            lambda: invoke_curl(
                url=f"{URL_BASE}/order/finish",
                headers=self.__get_session_headers(),
            ),
            logger=self._logger.getChild("__get_order_details"),
        )
        vendor_po = re.search(r"saleNum.*?(\d+)", stdout).group(1)
        payment_account = re.search(r"ipgumAccountNo.*?(\d+)", stdout).group(1)
        total = re.search(r"ipgumAmt.*?(\d+)", stdout).group(1)
        return {
            'vendor_po': vendor_po,
            'payment_account': payment_account,
            'total_price': total
        }

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
        ordered_products = []
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
                    raise ProductNotAvailableError(product_id)
                if product.get('stockExistYn') == 'N':
                    raise ProductNotAvailableError(product_id)
                op.product.separate_shipping = bool(int(
                    product.get("isIndividualDelivery") or 0
                ))
                
                ordered_products.append((op,))
                self.__goodsList.append({
                    'seq': len(self.__goodsList),
                    "goodsNo": product['goodsNo'],
                    "itemNo": option,
                    "ordQty": op.quantity,
                    "lowVendNo": "LV01",
                    "salePrice": op.price,
                    "warehouseNo": "01",
                    'seqNo': str(len(self.__goodsList)).zfill(6),
                    "dlvpSeq": 0,
                    "beneSeqList": [1]
                })
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
        # self.__add_to_cart(cart)
        if len(ordered_products) == 0:
            raise PurchaseOrderError(
                self.__purchase_order,
                self,
                f"No available products are in the PO. Unavailable products:\n{unavailable_products}",
            )
        return ordered_products, unavailable_products

    def __get_product_by_id(self, product_id):
        try:
            result = get_html(
                url=f"{URL_BASE}/goods/goodsResult",
                # resolve="www.atomy.kr:443:13.209.185.92,3.39.241.190",
                headers=self.__get_session_headers(),
                raw_data=urlencode({
                    "pagingYn": "N",
                    "pageIdx": 1,
                    "rowsPerPage": 15,
                    "searchKeyword": product_id,
                    "index": 0
                })
            )

            if len(result.cssselect('div#goodsPagedList_none')) > 0:
                # The product with such a code doesn't exist
                return None, None
            product_info = json.loads(result.cssselect('input#goodsInfo_0')[0].attrib['data-goodsinfo'])
            base_product_id = product_info['goodsNo']
            option = (
                self.__get_product_option(base_product_id, product_id)
                    if (len(result.cssselect('button[option-role]'))) > 0
                    else '00000'
            )
            return product_info, option
        except HTTPError:
            self._logger.warning(
                "Product %s: Couldn't get response from Atomy server in several attempts. Giving up",
                product_id,
            )
        return None, None

    def __get_product_option(self, product, option_id):
        result = get_json(
            url=f"{URL_BASE}/goods/itemStatus",
            headers=self.__get_session_headers() + [{"content-type": "application/x-www-form-urlencoded"}],
            raw_data=urlencode({'goodsNo': product, 'goodsTypeCd': '101'})
        )
        return [
            o
            for o in result.values()
            if o["materialCode"] == option_id
        ][0]["itemNo"]

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
        self.__mst["saleDate"] = sale_date.strftime("%Y%m%d")

    def __set_local_shipment(
        self,
        purchase_order: PurchaseOrder,
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
            logger.debug("Setting combined shipment params")
            self.__mst["deliCostDiviCd"] = "1"
            self.__mst["packingNo"] = (
                f"{purchase_order.contact_phone}/{purchase_order.address.zip}"
            )
            self.__mst["packingYn"] = "Y"
            self.__dlvpList[0][
                "packingMemo"
            ] = f"{purchase_order.contact_phone}/{purchase_order.address.zip}"
            self.__beneList[0]["deliCostDiviCd"] = "1"
        else:
            logger.debug("No combined shipment is needed")

    def __get_order_id(self, purchase_order: PurchaseOrder) -> str:
        order_id_parts = purchase_order.id[8:].split("-")
        return (
            order_id_parts[2][1:] + "ㅡ" + order_id_parts[1] + "ㅡ" + order_id_parts[0]
        )

    def __set_receiver_mobile(self, phone="     "):
        logger = self._logger.getChild("__set_receiver_mobile")
        logger.debug("Setting receiver phone number")
        self.__mst["cellNo"] = phone.replace("-", "")
        self.__dlvpList[0]["cellNo"] = phone

    def __set_receiver_address(self, address: Address, phone, order_id):
        logger = self._logger.getChild("__set_receiver_address")
        logger.debug("Setting shipment address")
        self.__mst['ordererNm'] = order_id
        self.__dlvpList[0] = {
            "count": 0,
            "deliFormCd": "10",
            "mbrDlvpSeq": "0000001",
            "dlvpDiviCd": "10",
            "baseYn": "Y",
            "dlvpNm": order_id,
            "recvrPostNo": address.zip,
            "recvrBaseAddr": address.address_1,
            "recvrDtlAddr": address.address_2,
            "cellNo": phone,
            "publicPlace": False,
            "express": False,
            "seq": 0,
            "dlvpNo": "1",
            "recvrNm": order_id,
            "buPlace": "",
            "deliTypeCd": "3",
            "packingMemo": None,
            "deliCostTaxRate": 0,
            "weekDeliveryPossYn": "N",
            "saleAmtDispYn": "Y",
        }

    def __set_payment_params(self, po: PurchaseOrder, ordered_products: list[tuple[OrderProduct, str]]):
        logger = self._logger.getChild("__set_payment_params")
        logger.debug("Setting payment parameters")
        total_krw = reduce(
            lambda acc, op: acc + (op[0].price * op[0].quantity), ordered_products, 
            0)
        pl = self.__po_params["payList"][0]
        pl["payAmt"] = total_krw
        pl["payVat"] = int(total_krw / 11)
        pl["bankCd"] = po.company.bank_id if po.company.bank_id != "06" else "04"
        pl["payerPhone"] = po.payment_phone
        pl["vanData"]["data"]["bankCd"] = po.company.bank_id
        pl["vanData"]["data"]["dispGoodsNm"] = po.order_products[0].product.name
        pl["vanData"]["data"]["ordererNm"] = po.customer.name
        pl["vanData"]["data"]["expiry"] = self.__get_payment_deadline()
        pl["vanData"]["payAmt"] = total_krw
        self.__payment_payload["ordData"]["payList"][0]["bankCd"] = pl["bankCd"]
        self.__payment_payload["ordData"]["payList"][0][
            "expiry"
        ] = self.__get_payment_deadline()

    def __get_payment_deadline(self) -> str:
        return (datetime.now() + timedelta(hours=47)).strftime("%Y%m%d%H0000")

    def __set_tax_info(self, purchase_order: PurchaseOrder):
        self._logger.debug("Setting counteragent tax information")
        if purchase_order.company.tax_id != ("", "", ""):  # Company is taxable
            if purchase_order.company.tax_simplified:
                self.__mst["cashReceiptIssueCd"] = "2"
                self.__mst["cashReceiptCertNo"] = "000{}-{}{}".format(
                    purchase_order.company.tax_id[0],
                    purchase_order.company.tax_id[1],
                    purchase_order.company.tax_id[2],
                )
                self.__payment_payload['ordData']["payList"][0]["registrationNumber"] = (
                    "000{}{}{}".format(
                        purchase_order.company.tax_id[0],
                        purchase_order.company.tax_id[1],
                        purchase_order.company.tax_id[2],
                    )
                )
                self.__po_params["payList"][0]["registrationNumber"] = \
                    self.__payment_payload['ordData']["payList"][0]["registrationNumber"]
                self.__po_params['payList'][0]['vanData']['data']["registrationNumber"] = \
                    self.__payment_payload['ordData']["payList"][0]["registrationNumber"]
            else:
                self.__mst["cashReceiptUseDiviCd"] = "3"
                del self.__mst["cashReceiptIssueCd"]
                self.__mst["cashReceiptCertNo"] = "{}-{}-{}".format(
                    purchase_order.company.tax_id[0],
                    purchase_order.company.tax_id[1],
                    purchase_order.company.tax_id[2],
                )
                self.__payment_payload["ordData"]["taxInfo"] = self.__get_atomy_company(purchase_order.company)
                self.__po_params['taxInfo'] = self.__get_atomy_company(purchase_order.company)

    def __get_atomy_company(self, company: Company) -> dict[str, Any]:
        logger = self._logger.getChild("__get_atomy_company")
        return {
            "type": "new",
            "bizNm": company.name,
            "taxMbrNm": company.contact_person,
            "bizNo": "{}{}{}".format(company.tax_id[0], company.tax_id[1], company.tax_id[2]),
            "industry": company.business_type,
            "bunic": company.business_category,
            "category": company.business_category,
            "postNo": company.address.zip,
            "baseAddr": company.address.address_1,
            "dtlAddr": company.address.address_2,
            "cellNo": company.tax_phone,
            "email": company.email,
            "contactNm": company.contact_person,
            "saveYn": "N"
        }
    
    def __submit_order(self):
        logger = self._logger.getChild("__submit_order")
        logger.info("Submitting the order")
        pay_no, sale_no = self.__send_payment_request()
        self.__send_order_post_request(pay_no, sale_no)
        vendor_po = self.__get_order_details()
        logger.debug("Created order: %s", vendor_po)
        return (
            vendor_po['vendor_po'],
            vendor_po["payment_account"],
            vendor_po["total_price"],
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
                purchase_order.set_status(ORDER_STATUSES[o["status"]])
                return purchase_order

        raise NoPurchaseOrderError(
            "No corresponding purchase order for Atomy PO <%s> was found"
            % purchase_order.vendor_po_id
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

    def __get_purchase_orders(self):
        logger = self._logger.getChild("__get_purchase_orders")
        logger.debug("Getting purchase orders")
        res = get_html(
            url=f"{URL_BASE}/mypage/orderList?"
            + "psearchMonth=12&startDate=&endDate=&orderStatus=all&pageIdx=2&rowsPerPage=100",
            headers=self.__get_session_headers() + [{"Cookie": "KR_language=en"}],
        )

        orders = [
            {
                'id': element.cssselect("input[name='hSaleNum']")[0].attrib['value'],
                'status': element.cssselect("span.m-stat")[0].text.strip()
            }
            for element in res.cssselect("div.my_odr_gds li")
        ]
        return orders
