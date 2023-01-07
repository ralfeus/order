import logging
import math
from operator import attrgetter

from app import db
from app.models import BaseModel, Country
from app.shipping.models import Shipping
from exceptions import NoShippingRateError

from .dhl_country import DHLCountry
from .dhl_rate import DHLRate
from .dhl_zone import DHLZone

# dhl_zones = db.Table('dhl_zones',
#     db.Column('id', db.Integer(), primary_key=True)
# )

class DHL(Shipping):
    '''DHL shipping'''
    __mapper_args__ = {'polymorphic_identity': 'dhl'}

    name = 'DHL'
    type = 'DHL'

    def can_ship(self, country: Country, weight: int, products: list = None) -> bool:
        if not self._are_all_products_shippable(products: list[str]):
            return False
        if weight and weight > 99999:
            return False
        if country is None:
            return True
        return DHLCountry.query.filter_by(country_id=country.id).first() is not None

    def get_edit_url(self):
        from .. import bp_client_admin
        return f"{bp_client_admin.url_prefix}/"

    def get_shipping_cost(self, destination, weight):
        logger = logging.getLogger("DHL::get_shipping_cost()")
        weight = int(weight) / 1000
        country = DHLCountry.query.get(destination)
        if country is None:
            raise NoShippingRateError
        rate = sorted(
            filter(lambda r: r.weight > weight, country.rates),
                   key=attrgetter('weight')
        )
        if len(rate) == 0:
            raise NoShippingRateError()
        rate = rate[0].rate
        if weight > 30:
            return rate * math.ceil(weight)

        logger.debug("Shipping rate for %skg parcel to %s is %s",
                     weight, destination, rate)
        return rate
