from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class ShippingRate(db.Model):
    '''
    Rate of the parcel shipping
    '''
    __tablename__ = 'shipping_rates'

    id = Column(Integer, primary_key=True)
    destination = Column(String(32), index=True)
    weight = Column(Integer, index=True)
    rate = Column(Float)

    def __repr__(self):
        return "<{}: {}/{}/{}>".format(type(self), self.destination, self.weight, self.rate)
