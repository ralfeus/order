from __future__ import annotations
import json
import logging
from operator import itemgetter
import re
import time
from typing import Any

from flask import current_app, url_for

from app import cache
from app.models import Country
import app.orders.models as o
from app.shipping.models import Shipping
from app.tools import first_or_default, get_json, invoke_curl
from exceptions import HTTPError, NoShippingRateError, OrderError

from app.shipping.models.consign_result import ConsignResult
from ..exceptions import EMSItemsException

hs_codes = {
    "Coffee": "0901902000",
    "Hair dryer": "1516310000",
    "Vitamin": "2106909099",
    "mask": "3307904000",
    "Skin": "3005909900",
    "Hair": "3305909000",
    "Face": "3304991000",
    "Cosmetic": "3304991000",
    "Shampoo": "3305100000",
    "Oral": "3306901000",
    "Detergent": "3402902000",
    "Beauty": "3924990090",
    "glove": "6116929000",
    "Cloth": "6211499000",
    "Household": "6912002000",
    "Kitchen": "8215999000",
    "Brush": "8545200000",
    "Sanitary": "9619001090",
    "_default_": "3304991000",
}


class EMS(Shipping):
    """EMS shipping"""

    __mapper_args__ = {"polymorphic_identity": "ems"}  # type: ignore

    name = "EMS"
    type = "EMS"

    __username = "sub1079"
    __password = "2045"

    def __invoke_curl(self, *args, **kwargs) -> tuple[str, str]:
        logger = logging.getLogger("EMS::__invoke_curl()")
        kwargs["headers"] = [self.__login()]
        for _ in range(0, 3):
            stdout, stderr = invoke_curl(*args, **kwargs)
            if re.search("HTTP.*? 401", stderr):
                logger.warning("EMS authentication error. Retrying...")
                kwargs["headers"] = [self.__login(force=True)]
            else:
                return stdout, stderr
        raise HTTPError(401)
    
    def _get_print_label_url(self):
        from .. import bp_client_admin
        return url_for(endpoint=f'{bp_client_admin.name}.admin_print_label')

    def can_ship(self, country: Country, weight: int, products: list[str] = []) -> bool:
        logger = logging.getLogger("EMS::can_ship()")
        if not self._are_all_products_shippable(products):
            logger.debug(f"Not all products are shippable to {country}")
            return False
        if weight and weight > 30000:
            logger.debug(f"The parcel is too heavy: {weight}g")
            return False
        if country is None:
            return True

        try:
            rates = get_rates(country)
        except:
            rates = []
        rates = sorted(
            [rate for rate in rates if rate["weight"] >= weight],
            key=itemgetter("weight"),
        )
        rate_exists = len(rates) > 0
        if rate_exists:
            logger.debug(f"There is a rate to country {country}. Can ship")
        else:
            logger.debug(f"There is no rate to country {country}. Can't ship")
        return rate_exists

    def consign(self, order, config={}):
        logger = logging.getLogger("EMS::consign()")
        try:
            if order is None:
                return
            if isinstance(config, dict) and \
            not (config.get('ems') is None or 
                    config['ems'].get('login') is None or 
                    config['ems'].get('password') is None):
                self.__username = config['ems']['login']
                self.__password = config['ems']['password']
                self.__login(force=cache.get(f'{current_app.config.get("TENANT_NAME")}:ems_user') != self.__username)
            consignment_id = self.__create_new_consignment()
            self.__save_consignment(consignment_id, order)
            self.__submit_consignment(consignment_id)
            logger.info("The order %s is consigned as %s", order.id, consignment_id)
            return ConsignResult(
                consignment_id=consignment_id, 
                next_step_message="Finalize shipping order and print label",
                next_step_url=f'{self._get_print_label_url()}?order_id={order.id}'
                    if order else '')
        except EMSItemsException as e:
            logger.warning(str(e))
            raise OrderError("Couldn't get EMS items description from the order")
    
    def print(self, order: o.Order, config: dict[str, Any]={}) -> dict[str, Any]:
        '''Prints shipping label to be applied too the parcel
        :param Order order: order, for which label is to be printed
        :param dic[str, Any] config: configuration to be used for 
        shipping provider
        :raises: :class:`NotImplementedError`: In case the consignment
        functionality is not implemented by a shipping provider
        :returns bytes: label file'''
        if order.tracking_id is None:
            raise AttributeError(f'Order {order.id} has no consignment created')
        if isinstance(config, dict) and \
           not (config.get('ems') is None or 
                config['ems'].get('login') is None or 
                config['ems'].get('password') is None):
            self.__username = config['ems']['login']
            self.__password = config['ems']['password']
            self.__login(force=cache.get(f'{current_app.config.get("TENANT_NAME")}:ems_user') != self.__username)
        logger = logging.getLogger("EMS::print()")
        logger.info("Getting consignment %s", order.tracking_id)
        try:
            code = self.__get_consignment_code(order.tracking_id)
            logger.debug(code)
            # uncomment for production, comment for development
            self.__print_label(code) 
            consignment = self.__get_consignment(code)
            return consignment
        except Exception as e:
            logger.warning(f"Couldn't print label for order {order.id}")
            raise e
    
    def __get_consignment(self, consignment_code: str) -> dict[str, Any]:
        return get_json(
            url=f'https://myems.co.kr/api/v1/order/print/code/{consignment_code}',
            get_data=self.__invoke_curl
        )
    
    def __get_consignments(self, url:str) -> list[dict[str, Any]]:
        logger = logging.getLogger('EMS::__get_consignments()')
        consignments = get_json(url=url, get_data=self.__invoke_curl)
        if len(consignments) != 2:
            logger.warning("Couldn't get consignment")
            logger.warning(consignments)
            return []
        return consignments[1] #type: ignore

    def __get_consignment_code(self, consignment_id: str) -> str:
        consignments = \
            self.__get_consignments(
                url='https://myems.co.kr/api/v1/order/orders/progress/A/offset/0') + \
            self.__get_consignments(
                url='https://myems.co.kr/api/v1/order/orders/progress/B/offset/0')
        for consignment in consignments:
            if isinstance(consignment, dict) and \
                consignment.get('ems_code') == consignment_id:
                return consignment['code']
        raise Exception(f"No consignment {consignment_id} was found")
    
    def __print_label(self, consignment: str):
        '''Submits request to print label. This makes the consignment obligatory 
        to be picked up and paid for
        :param consignment str: an internal code of a consignment to be printed'''
        logger = logging.getLogger("EMS::__get_print_label()")
        output, _ = self.__invoke_curl(
            f'https://myems.co.kr/b2b/order_print.php?type=declaration&codes={consignment}')
        # logger.debug(output)
        # logger.debug(_)

    def __create_new_consignment(self) -> str:
        logger = logging.getLogger("EMS::__create_new_consignment()")
        result, _ = self.__invoke_curl(
            url="https://myems.co.kr/api/v1/order/temp_orders/new", method="PUT"
        )
        logger.info("The new consignment ID is: %s", result)
        return result[1:-1]

    def __get_consignment_items(self, order: o.Order) -> list[dict[str, Any]]:
        def verify_consignment_items(items):
            for item in items:
                if not (
                    isinstance(item['quantity'], int) and
                    isinstance(item['price'], float) and 
                    len(item['hscode']) == 10):
                    raise EMSItemsException(items)
        logger = logging.getLogger("EMS::__get_consignment_items()")
        result: list[dict] = []
        try:
            items: list[str] = (
                order.params["shipping.items"].replace("|", "/").splitlines()
            )
            result = [
                {
                    "name": item.split("/")[0].strip(),
                    "quantity": item.split("/")[1].strip(),
                    "price": item.split("/")[2].strip(),
                    "hscode": hs_codes[
                        first_or_default(
                            list(hs_codes.keys()),
                            lambda i, ii=item: re.search(i, ii, re.I) is not None,
                            "_default_",
                        )
                    ],
                }
                for item in items
            ]
        except (KeyError, IndexError):
            logger.warning("Couldn't get items from:")
            logger.warning(order.params.get("shipping.items"))
            result = [
                {
                    "name": "Cosmetics",
                    "quantity": 1,
                    "price": order.total_usd / 10,
                    "hscode": "3304991000",
                }
            ]
        verify_consignment_items(result) 
        return result

    def __save_consignment(self, consignment_id: str, order: o.Order):
        logger = logging.getLogger("EMS::__save_consignment()")
        logger.info("Saving a consignment %s", consignment_id)
        payee = order.get_payee()
        if payee is None:
            raise OrderError("Order is not paid. Can't send")
        sender_phone = payee.phone.split("-")
        volume_weight = 0
        try:
            box = {
                "length": int(order.boxes[0].length),
                "width": int(order.boxes[0].width),
                "height": int(order.boxes[0].height),
                "weight": int(order.boxes[0].weight),
            }
        except Exception:
            logger.info("The box information is absent. Using default values")
            box = {
                "length": 42,
                "width": 30,
                "height": 19,
                "weight": order.total_weight + order.shipping_box_weight,
            }
            
        volume_weight = int(int(box["width"] * box["length"] * box["height"]) / 6)
        weight = max(box["weight"], volume_weight)
        price = self.__get_rate(order.country_id, weight)
        items = self.__get_consignment_items(order)
        request_payload = {
            "ems_code": consignment_id,
            "user_select_date": None,
            "p_hp1": sender_phone[0],  # sender phone number
            "p_hp2": sender_phone[1],  # sender phone number
            "p_hp3": sender_phone[2],  # sender phone number
            "p_name": payee.contact_person,  # sender name
            "p_post": payee.address.zip,  # sender zip code
            "p_address": payee.address.address_1_eng
            + " "
            + payee.address.address_2_eng,  # sender address
            "f_hp": order.phone,  # recipient phone number
            "f_name": order.customer_name,  # recipient name
            "f_post": order.zip,  # recipient zip code
            "f_address": order.address,  # recipient address
            "nation": order.country_id.upper(),  # recipient country
            "item_name": ";".join(
                [i["name"] for i in items]
            ),  # names of items separated by ';'
            "item_count": ";".join(
                [str(i["quantity"]) for i in items]
            ),  # quantities of items separated by ';'
            "item_price": ";".join(
                [str(int(i["price"])) for i in items]
            ),  # prices of items separated by ';'
            "item_hscode": ";".join(
                [i["hscode"] for i in items]
            ),  # HS codes of items separated by ';'
            "item_name1": "",  # probably can be omited
            "item_name2": "",  # probably can be omited
            "item_name3": "",  # probably can be omited
            "p_weight": weight,  # overall weight of the content
            "ems_price": "",  # leave empty
            "post_price": price["post_price"],  # get price from calculation service
            "n_code": order.country_id.upper(),  # recipient country
            "extra_shipping_charge": price[
                "extra_shipping_charge"
            ],  # get additional fee from calculation service
            "vol_weight1": box["width"],  # width
            "vol_weight2": box["length"],  # length
            "vol_weight3": box["height"],  # height
            "vol_weight": volume_weight,  # volume translated to weight. Calculated as width * length * height / 6
            # p_weight (above) is either itself of this value, if this value is bigger
            "item_detailed": "32",  # type of parcel 1 - Merch, 31 - gift, 32 - sample
        }
        logger.debug(request_payload)
        stdout, stderr = self.__invoke_curl(
            url="https://myems.co.kr/api/v1/order/temp_orders",
            raw_data=json.dumps(request_payload),
        )
        # logger.debug(stdout)
        # logger.debug(stderr)

    def __submit_consignment(self, consignment_id):
        logger = logging.getLogger("EMS::__submit_consignment")
        logger.info("Submitting consignment %s", consignment_id)
        stdout, stderr = self.__invoke_curl(
            url="https://myems.co.kr/api/v1/order/new", raw_data=f'["{consignment_id}"]'
        )
        # logger.debug(stdout)
        # logger.debug(stderr)

    def get_shipping_cost(self, destination, weight):
        logger = logging.getLogger("EMS::get_shipping_cost()")
        result = self.__get_rate(destination.upper(), weight)
        rate = int(result["post_price"]) + int(result.get("extra_shipping_charge") or 0)

        logger.debug(
            "Shipping rate for %skg parcel to %s is %s",
            weight / 1000,
            destination,
            rate,
        )
        return rate

    def __get_rate(self, country: str, weight: int) -> dict[str, Any]:
        """Return raw price structure from EMS"""
        logger = logging.getLogger("EMS::__get_rate()")
        id = self.__get_shipping_order()
        try:
            result = get_json(
                f"https://myems.co.kr/api/v1/order/calc_price/ems_code/{id}/n_code/{country}/weight/{weight}/premium/N",
                get_data=self.__invoke_curl,
            )
            return result
        except:
            raise NoShippingRateError()

    def __get_shipping_order(self, force=False, attempts=3):
        logger = logging.getLogger("EMS::__get_shipping_order()")
        if cache.get("ems_shipping_order") is None or force:
            result: list[list] = get_json(
                "https://myems.co.kr/api/v1/order/temp_orders",
                get_data=self.__invoke_curl,
            ) #type: ignore
            if result[0][0]["cnt"] == "0":
                id, _ = self.__invoke_curl(
                    "https://myems.co.kr/api/v1/order/temp_orders/new"
                )
            else:
                id = result[1][0]["ems_code"]
            cache.set("ems_shipping_order", id, timeout=28800)
        return cache.get("ems_shipping_order")

    def __login(self, force=False):
        logger = logging.getLogger("EMS::__login()")
        if cache.get("ems_login_in_progress"):
            logger.info("Another login process is running. Will wait till the end")
            logger.info("and use newly generated token")
            timeout = 20
            while cache.get("ems_login_in_progress") and not timeout:
                time.sleep(1)
                timeout -= 1
            if cache.get("ems_login_in_progress"):
                logger.warning(
                    "Waiting for another login process to complete has timed out"
                )
                logger.warning("will clear login semaphore and exit")
                cache.delete("ems_login_in_progress")
                return None
            logger.info("Another login process has finished. Will use existing token")
            logger.info(self.__username, cache.get(f"ems_auth:{self.__username}"))
            force = False
        logger.debug("%s, %s, %s", self.__username, 
                     cache.get(f"ems_auth:{self.__username}"), force)
        if cache.get(f"ems_auth:{self.__username}") is None or force:
            logger.info("Logging in to EMS as %s", self.__username)
            cache.set("ems_login_in_progress", True)
            result: list[dict] = get_json(
                url="https://myems.co.kr/api/v1/login",
                raw_data=f'{{"user":{{"userid":"{self.__username}","password":"{self.__password}"}}}}',
                method="POST",
            ) #type: ignore
            cache.set(f"ems_auth:{self.__username}", result[1]["authorizationToken"], 
                      timeout=28800)
            cache.set(f'ems_user:{self.__username}', self.__username, 
                      timeout=28800)
            logger.debug("Auth result: %s, %s", self.__username, 
                         cache.get(f"ems_auth:{self.__username}"))
            cache.delete("ems_login_in_progress")
        return {"Authorization": cache.get(f"ems_auth:{self.__username}")}


def __get_rates(country, url: str) -> list[dict]:
    if isinstance(country, Country):
        country_code = country.id.upper()
    elif isinstance(country, str):
        country_code = country.upper()
    else:
        raise NoShippingRateError("Unknown country")
    try:
        result = get_json(url=url.format(country_code), retry=False)
        rates: list[dict] = result["charge_info"]
        weight_limit = int(result["country_info"]["weight_limit"]) * 1000
        return [
            {"weight": int(rate["code_name2"]), "rate": int(rate["charge"])}
            for rate in rates
            if int(rate["code_name2"]) <= weight_limit
        ]
    except:
        raise NoShippingRateError


def get_rates(country):
    return __get_rates(
        country, "https://myems.co.kr/api/v1/common/emsChargeList/type/EMS/country/{}"
    )


def get_premium_rates(country):
    return __get_rates(
        country,
        "https://myems.co.kr/api/v1/common/emsChargeList/type/PREMIUM/country/{}",
    )
