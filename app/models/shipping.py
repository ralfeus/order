'''
Shipping method model
'''
from functools import reduce

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app import db
from app.models import ShippingRate
from app.models.base import BaseModel

box_weights = {
    30000: 2200,
    20000: 1900,
    15000: 1400,
    10000: 1000,
    5000: 500,
    2000: 250
}

class Shipping(db.Model, BaseModel):
    '''
    Shipping method model
    '''
    __tablename__ = 'shipping'

    name = Column(String(16))
    discriminator = Column(String(50))
    rates = relationship('ShippingRate')

    __mapper_args__ = {'polymorphic_on': discriminator}

    def get_shipment_cost(self, destination, weight):
        '''
        Returns shipping cost to provided destination for provided weight

        :param destination: destination (mostly country)
        :param weight: shipment weight in grams
        '''
        for rate in ShippingRate.query \
                    .filter_by(shipping_method_id=self.id, destination=destination) \
                    .order_by(ShippingRate.weight):
            if weight <= rate.weight:
                return rate.rate
        raise Exception("No rates found")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

    @staticmethod
    def get_box_weight(package_weight):
        return reduce(
            lambda acc, box: box[1] if package_weight < box[0] else acc,
            box_weights.items(), 0
        ) if package_weight > 0 \
        else 0

class NoShipping(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'noshipping'}
    @property
    def name(self):
        return 'No shipping'

    def get_shipment_cost(self, destination, weight):
        return 0
