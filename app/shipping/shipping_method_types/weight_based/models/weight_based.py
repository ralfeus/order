'''
Weight based shipping method type
'''
import math

from sqlalchemy.orm import relationship

from app import db
from app.shipping.models import Shipping
from app.shipping.shipping_method_types.weight_based.models import WeightBasedRate

class WeightBased(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'weight_based'}

    rates = relationship('WeightBasedRate')

    def get_shipping_cost(self, destination, weight):
        rate = rates.
        cost_per_unit = props['cost_per_kg'] / 1000 * props['weight_step']
        units = math.ceil(weight / props['weight_step'])
        return cost_per_unit * units