from __future__ import annotations
from functools import reduce
import json
import logging
from operator import itemgetter
import re
import time
from typing import Any

from flask import current_app, url_for

from app import cache
from app.models import Country
from app.models.address import Address
import app.orders.models as o
from app.shipping.models.box import Box
from app.shipping.models.shipping import Shipping
from app.shipping.models.shipping_contact import ShippingContact
from app.shipping.models.shipping_item import ShippingItem
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

BASE_URL = "https://www.myems.co.kr/api/v1/"


class EMS(Shipping):
    """EMS shipping"""

    __mapper_args__ = {"polymorphic_identity": "ems"}  # type: ignore

    name = "EMS"
    type = "EMS"

    _consign_implemented = True
    __username = "sub1079"
    __password = "2045"

    def __invoke_curl(self, *args, **kwargs) -> tuple[str, str]:
        logger = logging.getLogger("EMS::__invoke_curl()")
        kwargs["headers"] = [self.__login()]
        kwargs['ignore_ssl_check'] = True
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

    def can_ship(self, country: str, weight: int, products: list[str] = []) -> bool:
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
        rates = [rate for rate in rates if weight is None or rate["weight"] >= weight]
        
        rate_exists = len(rates) > 0
        if rate_exists:
            logger.debug(f"There is a rate to country {country}. Can ship")
        else:
            logger.debug(f"There is no rate to country {country}. Can't ship")
        return rate_exists

    def consign(self, sender: Address, sender_contact: ShippingContact, 
                recipient: Address, rcpt_contact: ShippingContact,
                items: list[ShippingItem], boxes: list[Box], config: dict[str, Any]={}):
        try:
            if isinstance(config, dict) and \
            not (config.get('ems') is None or 
                    config['ems'].get('login') is None or 
                    config['ems'].get('password') is None):
                self.__username = config['ems']['login']
                self.__password = config['ems']['password']
                self.__login(force=cache.get(f'{current_app.config.get("TENANT_NAME")}:ems_user') != self.__username)
            consignment_id = self.__create_new_consignment()
            self.__save_consignment(consignment_id, sender, sender_contact, 
                                    recipient, rcpt_contact, items, boxes)
            tracking_id = self.__submit_consignment(consignment_id)
            logging.info("The %s to %s is created", consignment_id, recipient)
            return ConsignResult(
                tracking_id=tracking_id, 
                next_step_message="Finalize shipping order and print label",
                next_step_url=f'{self._get_print_label_url()}?tracking_id={tracking_id}'
            )
        except EMSItemsException as e:
            logging.warning(str(e))
            raise OrderError("Couldn't get EMS items description from the order")
    
    def print(self, shipping_id: str, config: dict[str, Any]={}) -> dict[str, Any]:
        '''Prints shipping label to be applied too the parcel
        :param str shipping_id: shipping, for which label is to be printed.
        Usually is tracking ID
        :param dic[str, Any] config: configuration to be used for
        shipping provider
        :raises: :class:`NotImplementedError`: In case the consignment
        functionality is not implemented by a shipping provider
        :returns bytes: label file'''
        if isinstance(config, dict) and \
           not (config.get('ems') is None or 
                config['ems'].get('login') is None or 
                config['ems'].get('password') is None):
            self.__username = config['ems']['login']
            self.__password = config['ems']['password']
            self.__login(force=cache.get(f'{current_app.config.get("TENANT_NAME")}:ems_user') != self.__username)
        logging.info("Getting consignment %s", shipping_id)
        try:
            code = self.__get_consignment_code(shipping_id)
            logging.debug(code)
            # uncomment for production, comment for development
            self.__print_label(code) 
            consignment = self.__get_consignment(code)
            return consignment
        except Exception as e:
            logging.warning(f"Couldn't print label for shipment {shipping_id}")
            raise e
    
    def __get_consignment(self, consignment_code: str) -> dict[str, Any]:
        return get_json(
            url=f'{BASE_URL}/order/print/code/{consignment_code}',
            get_data=self.__invoke_curl
        )
    
    def __get_consignments(self, url:str) -> list[dict[str, Any]]:
        consignments = get_json(url=url, get_data=self.__invoke_curl)
        if len(consignments) != 2:
            logging.warning("Couldn't get consignment")
            logging.warning(consignments)
            return []
        return consignments[1] #type: ignore

    def __get_consignment_code(self, consignment_id: str) -> str:
        consignments = \
            self.__get_consignments(
                url=f'{BASE_URL}/order/orders/progress/A/offset/0') + \
            self.__get_consignments(
                url=f'{BASE_URL}/order/orders/progress/B/offset/0')
        for consignment in consignments:
            if isinstance(consignment, dict) and \
                consignment.get('ems_code') == consignment_id:
                return consignment['code']
        raise Exception(f"No consignment {consignment_id} was found")
    
    def __print_label(self, consignment: str):
        '''Submits request to print label. This makes the consignment obligatory 
        to be picked up and paid for
        :param consignment str: an internal code of a consignment to be printed'''
        output, _ = self.__invoke_curl(
            f'https://myems.co.kr/b2b/order_print.php?type=declaration&codes={consignment}')
        # logger.debug(output)
        # logger.debug(_)

    def __create_new_consignment(self) -> str:
        result, _ = self.__invoke_curl(
            url=f'{BASE_URL}/order/temp_orders/new', method="POST"
        )
        logging.info("The new consignment ID is: %s", result)
        return result[1:-1]

    def get_shipping_items(self, items: list[str]) -> list[ShippingItem]:
        def verify_consignment_items(items: list[ShippingItem]):
            for item in items:
                try:
                    if len(item.attributes['hscode']) != 10:
                        raise EMSItemsException({'hscode': item.attributes['hscode']})
                except Exception as e:
                    raise EMSItemsException(e, items)
        logger = logging.getLogger("EMS::__get_consignment_items()")
        result = []
        try:
            result = [ShippingItem(
                name=item.split("/")[0].strip(),
                quantity=int(item.split("/")[1].strip()),
                price=float(item.split("/")[2].strip()),
                weight=0,
                hscode=hs_codes[
                    first_or_default(
                        list(hs_codes.keys()),
                        lambda i, ii=item: re.search(i, ii, re.I) is not None,
                        "_default_",
                    )]
                )
                for item in items
            ]
        except (KeyError, IndexError):
            logger.warning("Couldn't get items from:")
            logger.warning(items)
            result = [ShippingItem(
                    name="Cosmetics",
                    quantity=1,
                    price=0,
                    weight=0,
                    hscode="3304991000"
            )]
        verify_consignment_items(result) 
        return result

    def __save_consignment(self, consignment_id: str, sender: Address, 
                           sender_contact: ShippingContact, recipient: Address, 
                           rcpt_contact: ShippingContact, items: list[ShippingItem], 
                           boxes: list[Box]):
        logging.info("Saving a consignment %s", consignment_id)
        total_weight = sum([i.weight for i in items])
        volume_weight = 0
        box = boxes[0]
        if 0 in [box.length, box.width, box.height]:
            logging.info("The box information is missing or incorrect. Using default values")
            box.length = 42
            box.width = 30
            box.height = 19
            box.weight = total_weight + box.weight
            
        volume_weight = int(int(box.width * box.length * box.height) / 6)
        weight = max(int(box.weight), volume_weight)
        price = self.__get_rate(recipient.country_id, weight)
        # items = self.get_shipping_items(items)
        sender_phone = sender_contact.phone.split("-")
        request_payload = {
            "code": consignment_id,
            "premium": "false",
            "document": "false",
            "user_select_date": None,
            "p_hp1": sender_phone[0],  # sender phone number
            "p_hp2": sender_phone[1],  # sender phone number
            "p_hp3": sender_phone[2],  # sender phone number
            "p_name": sender_contact.name,  # sender name
            "p_post": sender.zip,  # sender zip code
            "p_address": sender.address_1_eng
                + " "
                + sender.address_2_eng,  # sender address
            "f_hp": rcpt_contact.phone,  # recipient phone number
            "f_name": rcpt_contact.name,  # recipient name
            "f_post": recipient.zip,  # recipient zip code
            "f_address": recipient.address_1_eng + ' ' + recipient.address_2_eng,  # recipient address
            "nation": recipient.country_id.upper(),  # recipient country
            "item_name": ";".join(
                [i.name for i in items]
            ),  # names of items separated by ';'
            "item_count": ";".join(
                [str(i.quantity) for i in items]
            ),  # quantities of items separated by ';'
            "item_price": ";".join(
                [str(int(i.price)) for i in items]
            ),  # prices of items separated by ';'
            "item_hscode": ";".join(
                [i.attributes["hscode"] for i in items]
            ),  # HS codes of items separated by ';'
            "item_name1": "",  # probably can be omited
            "item_name2": "",  # probably can be omited
            "item_name3": "",  # probably can be omited
            "p_weight": weight,  # overall weight of the content
            "post_price": price["post_price"],  # get price from calculation service
            "n_code": recipient.country_id.upper(),  # recipient country
            "nation": recipient.country_id.upper(),  # recipient country
            "vol_weight1": box.width,  # width
            "vol_weight2": box.length,  # length
            "vol_weight3": box.height,  # height
            "vol_weight": volume_weight,  # volume translated to weight. Calculated as width * length * height / 6
            "extra_shipping_charge": price[
                "extra_shipping_charge"
            ],  # get additional fee from calculation service
            "item_detailed": "31",  # type of parcel 1 - Merch, 31 - gift, 32 - sample
        }
        logging.debug(request_payload)
        stdout, stderr = self.__invoke_curl(
            url=f'{BASE_URL}/order/temp_orders',
            method="PUT",
            raw_data=json.dumps(request_payload),
        )
        logging.debug(stdout)
        # logging.debug(stderr)

    def __submit_consignment(self, consignment_id):
        logger = logging.getLogger("EMS::__submit_consignment")
        logger.info("Submitting consignment %s", consignment_id)
        result = get_json(
            url=f'{BASE_URL}/order/new', raw_data=f'["{consignment_id}"]',
            get_data=self.__invoke_curl
        )

        logger.debug(result)
        if result.get('success') and (isinstance(result['success'], list)) and len(result['success']) > 0:
            logger.info("Consignment %s is submitted successfully. Tracking ID is %s", 
                        consignment_id, result['success'][0]['emsCode'])
            return result['success'][0]['emsCode']
        else:
            logger.warning("Couldn't submit consignment %s", consignment_id)
            logger.warning(result)
            raise Exception("Couldn't submit consignment to EMS")

    def get_shipping_cost(self, destination, weight):
        logger = logging.getLogger("EMS::get_shipping_cost()")
        result = self.__get_rate(destination.upper(), weight)
        try:
            rate = int(result["post_price"]) + int(result.get("extra_shipping_charge") or 0)

            logger.debug(
                "Shipping rate for %skg parcel to %s is %s",
                weight / 1000,
                destination,
                rate,
            )
            return rate
        except Exception:
            logger.info("Couldn't get rate for %skg parcel to %s", 
                        weight / 1000, destination)
            logger.info(result)
            raise NoShippingRateError()

    def __get_rate(self, country: str, weight: int) -> dict[str, Any]:
        """Return raw price structure from EMS"""
        logger = logging.getLogger("EMS::__get_rate()")
        try:
            result = get_json(
                f'{BASE_URL}/order/calc_price/n_code/{country}/weight/{weight}/premium/N/document/N',
                get_data=self.__invoke_curl,
            )
            return result
        except:
            raise NoShippingRateError()

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
            logger.info("%s, %s", self.__username, cache.get(f"ems_auth:{self.__username}"))
            force = False
        logger.debug("%s, %s, %s", self.__username, 
                     cache.get(f"ems_auth:{self.__username}"), force)
        if cache.get(f"ems_auth:{self.__username}") is None or force:
            logger.info("Logging in to EMS as %s", self.__username)
            cache.set("ems_login_in_progress", True)
            result: list[dict] = get_json(
                url=f'{BASE_URL}/login',
                raw_data=f'{{"user":{{"userid":"{self.__username}","password":"{self.__password}"}}}}',
                method="POST", ignore_ssl_check=True
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
    #TODO: Remove when MyEMS supports Lithuania
    if country_code == 'LT':
        country_code = 'PL'
    try:
        result = get_json(url=url.format(country_code), retry=False, ignore_ssl_check=True)
        rates: list[dict] = result["charge_info"]
        weight_limit = int(result["country_info"]["weight_limit"]) * 1000
        return [
            {"weight": int(rate["code_name2"]), "rate": int(rate["charge"])}
            for rate in rates
            if int(rate["code_name2"]) <= weight_limit or weight_limit == 0
        ]
    except:
        raise NoShippingRateError


def get_rates(country):
    return __get_rates(
        country, f'{BASE_URL}/common/emsChargeList/type/EMS/country/{{}}'
    )


def get_premium_rates(country):
    return __get_rates(
        country,
        f'{BASE_URL}/common/emsChargeList/type/PREMIUM/country/{{}}',
    )
