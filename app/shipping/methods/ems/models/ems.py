import logging
from operator import itemgetter

from app.models import Country
from app.shipping.models import Shipping
from app.tools import get_json
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
        weight = int(weight)
        rates = sorted(
            [rate for rate in get_rates(destination) if rate['weight'] >= weight],
            key=itemgetter('weight'), 
        )
        if len(rates) == 0:
            raise NoShippingRateError()
        rate = rates[0]['rate']

        logger.debug("Shipping rate for %skg parcel to %s is %s",
                     weight, destination, rate)
        return rate

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