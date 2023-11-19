import logging
from operator import itemgetter

from app import cache
from app.models import Country
from app.shipping.models import Shipping
from app.tools import get_json, invoke_curl
from exceptions import NoShippingRateError

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
        
        rates = get_rates(country)
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
                     weight, destination, rate)
        return rate

    session: list[dict[str, str]] = []
    def __get_rate(self, country: str, weight: int) -> int:
        if not self.session:
            self.session = [self.__login()]
        result = get_json('https://myems.co.kr/api/v1/order/temp_orders', 
                          headers=self.session)
        if result[0][0]['cnt'] == '0':
            id, _ = invoke_curl(
                'https://myems.co.kr/api/v1/order/temp_orders/new', 
                headers=self.session)
        else:
            id = result[1][0]['ems_code']
        result = get_json(
            f'https://myems.co.kr/api/v1/order/calc_price/ems_code/{id}/n_code/{country}/weight/{weight}/premium/N', 
            headers=self.session)
        return int(result['post_price'])

    @cache.cached(timeout=120)
    def __login(self):
        result = get_json(url='https://myems.co.kr/api/v1/login',
                        raw_data='{"user":{"userid":"sub1079","password":"2045"}}',
                        method='POST')
        return {'Authorization': result[1]['authorizationToken']}

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