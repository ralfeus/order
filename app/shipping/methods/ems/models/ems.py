import json
import logging
from operator import itemgetter
import time

from app import cache
from app.models import Country
from app.shipping.models import Shipping
from app.tools import get_json, invoke_curl
from exceptions import HTTPError, NoShippingRateError

class EMS(Shipping):
    '''EMS shipping'''
    __mapper_args__ = {'polymorphic_identity': 'ems'} #type: ignore

    name = 'EMS' #type: ignore
    type = 'EMS'

    def can_ship(self, country: Country, weight: int, products: list[str]=[]) -> bool:
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
            [rate for rate in rates if rate['weight'] >= weight],
            key=itemgetter('weight'), 
        )
        rate_exists = len(rates) > 0
        if rate_exists:
            logger.debug(f"There is a rate to country {country}. Can ship")
        else:
            logger.debug(f"There is no rate to country {country}. Can't ship")
        return rate_exists

    def get_shipping_cost(self, destination, weight):
        logger = logging.getLogger("EMS::get_shipping_cost()")
        rate = self.__get_rate(destination.upper(), weight)

        logger.debug("Shipping rate for %skg parcel to %s is %s",
                     weight / 1000  , destination, rate)
        return rate

    def __get_rate(self, country: str, weight: int) -> int:
        logger = logging.getLogger('EMS::__get_rate()')
        session = [self.__login()]
        id = self.__get_shipping_order()
        try:
            result = get_json(
                f'https://myems.co.kr/api/v1/order/calc_price/ems_code/{id}/n_code/{country}/weight/{weight}/premium/N', 
                headers=session)
            return int(result['post_price']) + int(result.get('extra_shipping_charge') or 0)
        except HTTPError as e:
            if e.status == 401:
                logger.warning("EMS authentication error. Retrying...")
                self.__login(force=True)
                return self.__get_rate(country, weight)
            raise
        except:
            raise NoShippingRateError()

    def __get_shipping_order(self, force=False, attempts=3):
        logger = logging.getLogger('EMS::__get_shipping_order()')
        if cache.get('ems_shipping_order') is None or force:
            session = [self.__login()]
            try:
                result = get_json('https://myems.co.kr/api/v1/order/temp_orders', 
                                headers=session)
                if result[0][0]['cnt'] == '0':
                    id, _ = invoke_curl(
                        'https://myems.co.kr/api/v1/order/temp_orders/new', 
                        headers=session)
                else:
                    id = result[1][0]['ems_code']
                cache.set('ems_shipping_order', id, timeout=28800)
            except HTTPError as e:
                if e.status == 401:
                    if attempts:
                        logger.warning("EMS authentication error. Retrying...")
                        self.__login(force=True)
                        return self.__get_shipping_order(force=force, attempts=attempts - 1)
        return cache.get('ems_shipping_order')

    def __login(self, force=False):
        logger = logging.getLogger("EMS::__login()")
        if cache.get('ems_login_in_progress'):
            logger.info('Another login process is running. Will wait till the end')
            logger.info('and use newly generated token')
            timeout = 20
            while cache.get('ems_login_in_progress') and not timeout:
                time.sleep(1)
                timeout -= 1
            if cache.get('ems_login_in_progress'):
                logger.warning("Waiting for another login process to complete has timed out")
                logger.warning("will clear login semaphore and exit")
                cache.delete('ems_login_in_progress')
                return None
            logger.info("Another login process has finished. Will use existing token")
            logger.info(cache.get('ems_auth'))
            force = False
        if cache.get('ems_auth') is None or force:
            logger.info("Logging in to EMS")
            cache.set('ems_login_in_progress', True)
            result = get_json(url='https://myems.co.kr/api/v1/login',
                            raw_data='{"user":{"userid":"sub1079","password":"2045"}}',
                            method='POST')
            cache.set('ems_auth', result[1]['authorizationToken'], timeout=28800)
            cache.delete('ems_login_in_progress')
        return {'Authorization': cache.get('ems_auth')}

def __get_rates(country, url: str) -> list[dict]:
    if isinstance(country, Country):
        country_code = country.id.upper()
    elif isinstance(country, str):
        country_code = country.upper()
    else:
        raise NoShippingRateError("Unknown country")
    try:
        result = get_json(
            url=url.format(country_code), 
            retry=False)
        rates: list[dict] = result['charge_info']
        weight_limit = int(result['country_info']['weight_limit']) * 1000
        return [ 
            {'weight': int(rate['code_name2']), 'rate': int(rate['charge'])} 
            for rate in rates if int(rate['code_name2']) <= weight_limit
        ]
    except:
        raise NoShippingRateError
    
def get_rates(country):
    return __get_rates(country, 'https://myems.co.kr/api/v1/common/emsChargeList/type/EMS/country/{}')

def get_premium_rates(country):
    return __get_rates(country, 'https://myems.co.kr/api/v1/common/emsChargeList/type/PREMIUM/country/{}')