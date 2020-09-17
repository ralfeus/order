'''
Shipping method model
'''
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models import ShippingRate
from app.models.base import BaseModel

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

class NoShipping(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'noshipping'}
    @property
    def name(self):
        return 'No shipping'

    def get_shipment_cost(self, destination, weight):
        return 0
