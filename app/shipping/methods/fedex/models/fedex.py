from __future__ import annotations
from functools import reduce
import json
import logging
import re
import time
from typing import Any

from flask import current_app

from app import cache
from app.models.address import Address
from app.models.country import Country
from app.orders.models.order import Order
from app.shipping.models import Shipping
from app.shipping.models.box import Box
from app.shipping.models.shipping_contact import ShippingContact
from app.shipping.models.shipping_item import ShippingItem
from app.tools import get_json, invoke_curl
from exceptions import HTTPError, NoShippingRateError, OrderError, ShippingException

from app.shipping.models.consign_result import ConsignResult
from ..exceptions import FedexConfigurationException, FedexItemsException, \
    FedexLoginException

class Fedex(Shipping):
    """Fedex shipping"""

    __mapper_args__ = {"polymorphic_identity": "fedex"}  # type: ignore

    name = "FedEx"
    type = "FedEx"

    _consign_implemented = True
    __zip = '08584'
    __src_country = 'KR'

    def __init__(self, test_mode=False):
        if test_mode:
            self.__base_url = 'https://apis-sandbox.fedex.com'
        else:
            self.__base_url = 'https://apis.fedex.com'
        try:
            config = current_app.config['SHIPPING_AUTOMATION']['fedex']
            self.__client_id = config['client_id']
            self.__client_secret = config['client_secret']
            self.__account = config['account']
            self.__service_type = config['service_type']

        except Exception as e:
            raise FedexConfigurationException(e)

    def __get_json(self, url, raw_data=None, headers: list=[], method='GET', 
                   retry=True, ignore_ssl_check=False) -> dict[str, Any]:
        logger = logging.getLogger("FedEx::__get_json()")
        
        def __invoke_curl(url: str, raw_data: str='', headers: list[dict[str, str]]=[],
                    method='GET', retries=2, ignore_ssl_check=False) -> tuple[str, str]:
            token = [self.__login()]
            for _ in range(0, 3):
                stdout, stderr = invoke_curl(url, raw_data, headers + token, method, 
                                            use_proxy=False, retries=retries, 
                                            ignore_ssl_check=ignore_ssl_check)
                if re.search("HTTP.*? 401", stderr):
                    logger.warning("FedEx authentication error. Retrying...")
                    token = [self.__login(force=True)]
                else:
                    return stdout, stderr
            raise HTTPError(401)
        
        return get_json(url, raw_data, 
                        headers=headers + [
                            {'Content-Type': "application/json"},
                            {'X-locale': "en_US"}], 
                        method=method, retry=retry, 
                        get_data=__invoke_curl, ignore_ssl_check=ignore_ssl_check)
    
    def __login(self, force=False) -> dict[str, str]:
        logger = logging.getLogger("FedEx::__login()")
        if cache.get("fedex_login_in_progress"):
            logger.info("Another login process is running. Will wait till the end")
            logger.info("and use newly generated token")
            timeout = 20
            while cache.get("fedex_login_in_progress") and not timeout:
                time.sleep(1)
                timeout -= 1
            if cache.get("fedex_login_in_progress"):
                logger.warning(
                    "Waiting for another login process to complete has timed out"
                )
                logger.warning("will clear login semaphore and exit")
                cache.delete("fedex_login_in_progress")
                raise FedexLoginException
            logger.info("Another login process has finished. Will use existing token")
            logger.info(cache.get("fedex_auth"))
            force = False
        # logger.debug("%s, %s", cache.get("fedex_auth"), force)
        if cache.get("fedex_auth") is None or force:
            logger.info("Logging in to FedEx")
            cache.set("fedex_login_in_progress", True)
            result: dict = get_json(
                url=f"{self.__base_url}/oauth/token",
                get_data=lambda url, method, raw_data, headers, retries, ignore_ssl_check: 
                    invoke_curl(url, 
                        raw_data=f'grant_type=client_credentials&client_id={self.__client_id}&client_secret={self.__client_secret}', 
                        ignore_ssl_check=True, use_proxy=False)
            ) #type: ignore
            cache.set("fedex_auth", result["access_token"], 
                      timeout=result['expires_in'])
            logger.debug("Auth result: %s", cache.get("fedex_auth"))
            cache.delete("fedex_login_in_progress")
        return {"Authorization": f"Bearer {cache.get('fedex_auth')}"}

    def _get_print_label_url(self):
        return ''

    def can_ship(self, country: Country, weight: int, products: list[str] = []) -> bool:
        logger = logging.getLogger("FedEx::can_ship()")
        if not self._are_all_products_shippable(products):
            logger.debug(f"Not all products are shippable to {country}")
            return False
        if weight and weight > 30000:
            logger.debug(f"The parcel is too heavy: {weight}g")
            return False
        if country is None:
            return True

        try:
            self.get_shipping_cost(country.id, 1)
            logger.debug(f"There is a rate to country {country}. Can ship")
            return True
        except NoShippingRateError:
            logger.debug(f"There is no rate to country {country}. Can't ship")
            return False

    def consign(self, sender: Address, sender_contact: ShippingContact, 
                recipient: Address, rcpt_contact: ShippingContact,
                items: list[ShippingItem], boxes: list[Box], config: dict[str, Any]={}
                ) -> ConsignResult:
        logger = logging.getLogger("FedEx::consign()")
        try:
            if sender is None or recipient is None or items is None:
                return
            sender = self.__validate_address(sender)
            recipient = self.__validate_address(recipient)
            payload = self.__prepare_shipment_request_payload(
                    sender, sender_contact, recipient, rcpt_contact, items, boxes)
            result = self.__get_json(
                url=f"{self.__base_url}/ship/v1/shipments",
                raw_data=json.dumps(payload)
            )
            if result.get('output') is None:
                raise ShippingException(result.get('alerts') or result.get('errors'))
            logger.info("The new consignment ID is: %s", result)
            shipmentObject = result['output']['transactionShipments'][0]
            return ConsignResult(
                tracking_id=shipmentObject['masterTrackingNumber'], 
                next_step_message="Print label",
                next_step_url=shipmentObject['pieceResponses'][0]['packageDocuments'][0]['url']
            )
        except FedexLoginException:
            logger.warning("Can't log in to Fedex")
            raise
        except FedexItemsException as e:
            logger.warning(str(e))
            raise OrderError("Couldn't get FedEx items description from the order")
        
    def is_consignable(self):
        return super().is_consignable()
        #TODO: add Fedex API availability (Rate API and Ship API)

    def __prepare_shipment_request_payload(self, sender, sender_contact, 
                                           recipient, rcpt_contact, 
                                           items: list[ShippingItem], boxes: list[Box]
                                           ) -> dict[str, Any]:
        total_value = self.__get_shipment_value(items)
        return {
            "labelResponseOptions": "URL_ONLY",
            'accountNumber': { 'value': self.__account },
            "requestedShipment": {
                "pickupType": "USE_SCHEDULED_PICKUP",
                'serviceType': self.__service_type,
                "packagingType": "YOUR_PACKAGING",
                "labelSpecification": {
                    "imageType": "PDF",
                    "labelStockType": "PAPER_4X6"
                },
                "shipper": {
                    "address": {
                        'streetLines': [sender.address_1_eng] if sender.address_2_eng is None
                            else [sender.address_1_eng, sender.address_2_eng],
                        'city': sender.city_eng,
                        'postalCode': sender.zip,
                        'countryCode': sender.country_id
                    },
                    "contact": {
                        'personName': sender_contact.name,
                        'phoneNumber': sender_contact.phone
                    }
                },
                'recipients': [{
                    'address': {
                        'streetLines': [recipient.address_1_eng] if recipient.address_2_eng is None
                            else [recipient.address_1_eng, recipient.address_2_eng],
                        'city': recipient.city_eng,
                        'postalCode': recipient.zip,
                        'countryCode': recipient.country_id
                    },
                    'contact': {
                        'personName': rcpt_contact.name,
                        'phoneNumber': rcpt_contact.phone
                    }
                }],
                "shippingChargesPayment": {
                    "paymentType": "SENDER"
                },
                "customsClearanceDetail": {
                    "dutiesPayment": {
                        "paymentType": "SENDER"
                    },
                    'totalCustomsValue': total_value,
                    "commodities": [{
                        "description": i.name,
                        "countryOfManufacture": "KR",
                        'weight': {
                            'units': 'KG',
                            'value': i.weight / 1000
                        },
                        "quantity": i.quantity,
                        "quantityUnits": "PCS",
                        'unitPrice': {
                            'amount': i.price,
                            'currency': 'WON'
                        },
                        "customsValue": {
                            "amount": i.price * i.quantity,
                            "currency": "WON"
                        }
                    }  for i in items]
                },
                "totalPackageCount": "1",
                "requestedPackageLineItems": [
                    {
                        "weight": {
                            "units": "KG",
                            'value': box.weight
                        },
                        "dimensions": {
                            "length": box.length,
                            "width": box.width,
                            "height": box.height,
                            "units": "CM"
                        }
                    }
                    for box in boxes
                ]
            }
        } 
    
    def __get_city_by_address(self, address: Address):
        result = self.__get_json(url=f"{self.__base_url}/caddress/v1/addresses/resolve", 
            raw_data=json.dumps({
                "addressesToValidate": [{
                    "address": {
                        "streetLines": [
                            address.address_1_eng, address.address_2_eng
                        ],
                        "postalCode": address.zip,
                        "countryCode": address.country_id
                    }
                }]
            }))
        if result.get('output') is None:
            raise ShippingException(f"Can't resolve the address: {address}")
        return result['output']['resolvedAddresses'][0]['city']
    
    def __validate_address(self, address: Address):
        if address.city_eng is None:
            address.city_eng = self.__get_city_by_address(address)
        return address
    
    def print(self, order: Order) -> dict[str, Any]:
        '''Prints shipping label to be applied too the parcel
        :param Order order: order, for which label is to be printed
        :param dic[str, Any] config: configuration to be used for 
        shipping provider
        :raises: :class:`NotImplementedError`: In case the consignment
        functionality is not implemented by a shipping provider
        :returns bytes: label file'''
        if order.tracking_id is None:
            raise AttributeError(f'Order {order.id} has no consignment created')
        self.__login()
        logger = logging.getLogger("FedEx::print()")
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
        
    def __print_label(self, consignment: str):
        '''Submits request to print label. This makes the consignment obligatory 
        to be picked up and paid for
        :param consignment str: an internal code of a consignment to be printed'''
        #TODO: complete
        logger = logging.getLogger("FedEx::__get_print_label()")
        output, _ = self.__invoke_curl(
            f'https://myems.co.kr/b2b/order_print.php?type=declaration&codes={consignment}')
        # logger.debug(output)
        # logger.debug(_)

    
    def __get_shipment_value(self, items: list[ShippingItem]):
        value = reduce(lambda acc, i: acc + i.quantity * i.price, items, 0.0)
        return {
            'amount': value,
            'currency': 'WON'
        }

    def get_shipping_items(self, items: list[str]) -> list[ShippingItem]:
        logger = logging.getLogger("FedEx::get_shipping_items()")
        result = []
        try:
            result = [ShippingItem(
                    name=item.split("/")[0].strip(),
                    quantity=int(item.split("/")[1].strip()),
                    price=float(item.split("/")[2].strip()),
                    weight=0
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
                    weight=0
            )]
        return result

    def get_shipping_cost(self, country, weight=1):
        logger = logging.getLogger("FedEx::get_shipping_cost()")
        try:
            result = self.__get_json(url=f'{self.__base_url}/rate/v1/rates/quotes', 
                raw_data=json.dumps({
                    'accountNumber': {
                        'value': self.__account
                    },
                    'requestedShipment': {
                        "rateRequestType": ["ACCOUNT"],
                        'shipper': {
                            'address': {
                                'postalCode': self.__zip,
                                'countryCode': self.__src_country
                            }
                        }, 
                        'recipient': {
                            'address': {
                                'postalCode': self.__get_zip(country),
                                'countryCode': country,
                            }
                        },
                        # 'serviceType': self.__service_type,
                        'pickupType': 'USE_SCHEDULED_PICKUP',
                        'requestedPackageLineItems': [
                            { 
                                'weight': {
                                    'units': 'KG',
                                    'value': weight / 1000
                                } 
                            }
                        ]
                    }
                }),
                retry=False, ignore_ssl_check=True)
            if result.get('output') is None:
                raise NoShippingRateError(result.get('errors'))
            rates = result["output"]["rateReplyDetails"]
            rate_objects = [
                r['ratedShipmentDetails'] for r in rates 
                if r['serviceType'] == self.__service_type]
            if len(rate_objects) == 0:
                raise NoShippingRateError(f"There are rates but no {self.__service_type}")
            rate = rate_objects[0][0]
            return int(rate.get('totalNetChargeWithDutiesAndTaxes')
                             or rate.get('totalNetFedExCharge')) #type: ignore
        except NoShippingRateError as e:
            logger.warning("There is no rate to %s of %sg package", country, weight)
            logger.warning(e)
            raise e
        except Exception as e:
            logger.error("During getting rate to %s of %sg package the error has occurred",
                         country, weight)
            logger.exception(e)
            raise NoShippingRateError

    def __get_zip(self, country_id: str) -> str:
        country = Country.query.get(country_id.lower())
        if country is None:
            raise ShippingException(f"<{country_id}> is not a valid country")
        return country.first_zip    
