'''
Weight based shipping method type
'''
import logging
import math

# from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship

from app.models import Country
from exceptions import NoShippingRateError
from app.shipping.models import Shipping
from .weight_based_rate import WeightBasedRate

class WeightBased(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'weight_based'}

    type = "Weight based"
    rates = relationship('WeightBasedRate', lazy='dynamic')

    def __get_rate(self, destination):
        if isinstance(destination, Country):
            destination = destination.id

        return self.rates.filter_by(destination=destination).first()

    def get_edit_url(self):
        from .. import bp_client_admin
        return f"{bp_client_admin.url_prefix}/{self.id}"

    def get_shipping_cost(self, destination, weight):
        logger = logging.getLogger("WeightBased::get_shipping_cost()")
        props = self.__get_rate(destination)
        if props is None:
            raise NoShippingRateError()
        if weight > props.maximum_weight:
            raise NoShippingRateError()
        cost_per_unit = props.cost_per_kg / 1000 * props.weight_step
        units = math.ceil(max(weight, props.minimum_weight) / props.weight_step)
        logger.debug("Shipping rate for %skg parcel to %s is %s",
                     weight, destination, cost_per_unit * units)
        return cost_per_unit * units
