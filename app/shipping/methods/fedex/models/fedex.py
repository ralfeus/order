from __future__ import annotations
import base64
from functools import reduce
import json
import logging
import os
import re
from tempfile import _TemporaryFileWrapper
import time
from typing import Any

from flask import current_app, url_for
from sqlalchemy.orm import relationship

from app import cache, db
from app.currencies.models.currency import Currency
from app.models.address import Address
from app.models.country import Country
from app.orders.models.order import Order
from app.shipping.methods.fedex.models.fedex_setting import FedexSetting
from app.shipping.models.box import Box
from app.shipping.models.shipping import Shipping
from app.shipping.models.shipping_contact import ShippingContact
from app.shipping.models.shipping_item import ShippingItem
from app.tools import get_json, invoke_curl
from exceptions import HTTPError, NoShippingRateError, ShippingException

from app.shipping.models.consign_result import ConsignResult
from ..exceptions import FedexConfigurationException, FedexLoginException

class Fedex(Shipping):
    """Fedex shipping"""

    __mapper_args__ = {"polymorphic_identity": "fedex"}  # type: ignore

    type = "FedEx"
    settings = relationship('FedexSetting', uselist=False, lazy='select')

    _consign_implemented = True
    __zip = '08584'
    __src_country = 'KR'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.settings is None:
            self.settings = FedexSetting(shipping_id=self.id)
            db.session.add(self.settings)
        try:
            config = current_app.config['SHIPPING_AUTOMATION']['fedex']
            self.__base_url = config['base_url']
            self.__client_id = config['client_id']
            self.__client_secret = config['client_secret']
            self.__account = config['account']

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
    
    def __get_service_availability(self, country_id: str) -> list[str]:
        '''Returns list of services available for the given country
        :param str country_id: ID of the country
        :returns list[str]: list of available services'''
        logger = logging.getLogger("FedEx::__get_service_availability()")
        country = Country.query.get(country_id)
        if country is None:
            return []
        payload = json.dumps({
            "requestedShipment": {
                "pickupType": "USE_SCHEDULED_PICKUP",
                "packagingType": "YOUR_PACKAGING",
                "shipper": {
                    "address": {
                        "streetLines": [
                            "SENDER ADDRESS LINE 1"
                        ],
                        "city": "Seoul",
                        "postalCode": "01000",
                        "countryCode": "KR"
                    }
                },
                "recipients": [
                    {
                        "address": {
                            "streetLines": [
                            ],
                            "city": country.capital,
                            "postalCode": country.first_zip,
                            "countryCode": country_id.upper()
                        }
                    }
                ],
                "customsClearanceDetail": {
                    "dutiesPayment": {
                        "paymentType": "SENDER"
                    },
                    "totalCustomsValue": {
                        "amount": "10",
                        "currency": "EUR"
                    },
                    "commodities": [
                        {
                            "description": "COMMODITY DESCRIPTION 1",
                            "countryOfManufacture": "KR",
                            "weight": {
                                "units": "KG",
                                "value": "1"
                            },
                            "quantity": 1,
                            "quantityUnits": "PCS",
                            "numberOfPieces": 1,
                            "unitPrice": {
                                "amount": "10",
                                "currency": "EUR"
                            },
                            "customsValue": {
                                "amount": "10",
                                "currency": "EUR"
                            }
                        }
                    ]
                },
                "requestedPackageLineItems": [
                    {
                        "weight": {
                            "units": "KG",
                            "value": "1"
                        }
                    }
                ]
            },
            "carrierCodes": ["FDXE"]
        })
        result = self.__get_json(url=f"{self.__base_url}/availability/v1/transittimes",
                                 raw_data=payload)
        if result.get('output') is None:
            logger.info(result.get('errors'))
            return []
        return [s['serviceType'] 
                for s in result['output']['transitTimes'][0]['transitTimeDetails']]

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
        from .. import bp_client_admin
        return url_for(endpoint=f'{bp_client_admin.name}.admin_print_label')

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

        services = self.__get_service_availability(country.id)
        if self.settings.service_type in services:
            logger.debug(f"Can ship to country {country}. ")
            return True
        else:
            logger.debug(f"Can't ship to country {country}.")
            return False

    def consign(self, sender: Address, sender_contact: ShippingContact, 
                recipient: Address, rcpt_contact: ShippingContact,
                items: list[ShippingItem], boxes: list[Box], config: dict[str, Any]={}
                ) -> ConsignResult:
        logger = logging.getLogger("FedEx::consign()")
        try:
            if sender is None or recipient is None or items is None:
                raise ShippingException("No sender or recipient or shipping items defined")
            payload = self.__prepare_shipment_request_payload(
                    sender, sender_contact, recipient, rcpt_contact, items, boxes)
            logger.debug(payload)
            result = self.__get_json(
                url=f"{self.__base_url}/ship/v1/shipments",
                raw_data=json.dumps(payload)
            )
            if result.get('output') is None:
                raise ShippingException(result.get('alerts') or result.get('errors'))
            logger.info("The new consignment ID is: %s", result)
            shipment_object = result['output']['transactionShipments'][0]
            self.__save_label(shipment_object['masterTrackingNumber'],
                # shipment_object['pieceResponses'][0]['packageDocuments'][0]['url'])
                shipment_object['pieceResponses'][0]['packageDocuments'][0]['encodedLabel'])
            return ConsignResult(
                tracking_id=shipment_object['masterTrackingNumber'], 
                next_step_message="Print label",
                next_step_url=f"{self._get_print_label_url()}?tracking_id={shipment_object['masterTrackingNumber']}"
                # next_step_url=shipment_object['pieceResponses'][0]['packageDocuments'][0]['url']
            )
        except FedexLoginException:
            logger.warning("Can't log in to Fedex")
            raise
        
    def is_consignable(self):
        return super().is_consignable()
        #TODO: add Fedex API availability (Rate API and Ship API)

    def __prepare_shipment_request_payload(
        self, sender, sender_contact, recipient, rcpt_contact, 
        items: list[ShippingItem], boxes: list[Box]) -> dict[str, Any]:
        total_value = self.__get_shipment_value(items)
        return {
            "labelResponseOptions": "LABEL",
            'accountNumber': { 'value': self.__account },
            "requestedShipment": {
                "pickupType": "USE_SCHEDULED_PICKUP",
                'serviceType': self.settings.service_type,
                "packagingType": "YOUR_PACKAGING",
                "labelSpecification": { 
                    "labelFormatType": "COMMON2D", 
                    "labelStockType": "PAPER_85X11_TOP_HALF_LABEL", 
                    "imageType": "PDF"
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
                            'value': box.weight / 1000
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
        
    def __save_label(self, tracking_id, encoded_label):
    # def __save_label(self, tracking_id, url):
        # stdout, _ = invoke_curl(url=url)
        label = base64.b64decode(encoded_label)
        fedex_upload_dir = os.path.join(
            os.getcwd(), 
            current_app.config['UPLOAD_PATH'], 
            'fedex')
        os.makedirs(fedex_upload_dir, exist_ok=True)
        with open(f'{fedex_upload_dir}/label-{tracking_id}.pdf', 'xb') as f:
            f.write(label)

    def __validate_address(self, address: Address):
        result = self.__get_json(url=f"{self.__base_url}/address/v1/addresses/resolve", 
            raw_data=json.dumps({
                "addressesToValidate": [{
                    "address": {
                        "streetLines": [
                            address.address_1_eng, address.address_2_eng
                        ],
                        "city": address.city_eng,
                        "postalCode": address.zip,
                        "countryCode": address.country_id
                    }
                }]
            }))
        if result.get('output') is None:
            raise ShippingException(f"Can't resolve the address: {address}")
        resolved_address = result['output']['resolvedAddresses'][0]
        address.address_1_eng = resolved_address['streetLinesToken'][0]
        address.address_2_eng = resolved_address['streetLinesToken'][1] \
            if len(resolved_address['streetLinesToken']) > 1 else ""
        address.city_eng = resolved_address['city']
        address.zip = resolved_address['postalCode']
        return address
    
    def print(self, order: Order) -> dict[str, Any]:
        '''Prints shipping label to be applied to the parcel
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

    def __get_shipment_value(self, items: list[ShippingItem]):
        value = reduce(lambda acc, i: acc + i.quantity * i.price, items, 0.0)
        return {
            'amount': value,
            'currency': 'WON'
        }
    
    def get_customs_label(self, order) -> tuple[_TemporaryFileWrapper, str]:
        #TODO
        return super().get_customs_label(order)

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
    
    def get_edit_url(self):
        from .. import bp_client_admin
        return f"{bp_client_admin.url_prefix}/{self.id}"

    def get_shipping_cost(self, country_id, weight=250):
        logger = logging.getLogger("FedEx::get_shipping_cost()")
        try:
            country: Country = Country.query.get(country_id)
            if country is None:
                raise NoShippingRateError()
            payload = {
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
                                'postalCode': country.first_zip,
                                'city': country.capital,
                                'countryCode': country.id.upper(),
                            }
                        },
                        'pickupType': 'USE_SCHEDULED_PICKUP',
                        'requestedPackageLineItems': [
                            { 
                                'weight': {
                                    'units': 'KG',
                                    'value': (weight if weight >= 3000 else min(weight * 1.15, 3000)) / 1000
                                } 
                            }
                        ]
                    }
                }
            result = self.__get_json(url=f'{self.__base_url}/rate/v1/rates/quotes', 
                raw_data=json.dumps(payload),
                retry=False, ignore_ssl_check=True)
            if result.get('output') is None:
                raise NoShippingRateError(result.get('errors'))
            rates = result["output"]["rateReplyDetails"]
            rate_objects = [
                r['ratedShipmentDetails'] for r in rates 
                if r['serviceType'] == self.settings.service_type]
            if len(rate_objects) == 0:
                raise NoShippingRateError(f"There are rates but no {self.settings.service_type}")
            rate_dict = rate_objects[0][0]
            rate = float(rate_dict.get('totalNetChargeWithDutiesAndTaxes')
                             or rate_dict.get('totalNetFedExCharge'))
            currency = Currency.query.get(rate_dict['currency'])
            if currency is None:
                raise NoShippingRateError(f"Unknown rate currency {rate_dict['currency']}")
            # Add 5% to cover future cost change
            rate = int(round(rate / float(currency.rate) * 1.05))
            logger.debug(
                "Shipping rate for %skg parcel to %s (service type: %s) is %s",
                weight / 1000,
                country_id,
                self.settings.service_type,
                rate,
            )
            return rate
        except NoShippingRateError as e:
            logger.warning("There is no rate to %s of %sg package", country_id, weight)
            logger.warning(e)
            raise e
        except Exception as e:
            logger.error("During getting rate to %s of %sg package the error has occurred",
                         country_id, weight)
            logger.exception(e)
            raise NoShippingRateError
        
    def to_dict(self):
        res = super().to_dict()
        return { **res,
            'service_type': self.settings.service_type
        }

def get_label(tracking_id: str) -> str:
    label_file_path = os.path.join(
                        os.getcwd(), 
                        current_app.config['UPLOAD_PATH'], 
                        f'fedex/label-{tracking_id}.pdf')
    if os.path.exists(label_file_path):
        return label_file_path
    else:
        raise FileNotFoundError(tracking_id)