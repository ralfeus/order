from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class ShippingRate(db.Model):
    '''
    Rate of the parcel shipping
    '''
    __tablename__ = 'shipping_rates'

    id = Column(Integer, primary_key=True)
    shipping_method_id = Column(Integer, ForeignKey('shipping.id'))
    shipping_method = relationship('Shipping', foreign_keys=[shipping_method_id])
    destination = Column(String(2), ForeignKey('countries.id'))
    weight = Column(Integer, index=True)
    rate = Column(Integer)

    def __repr__(self):
        return f"<{type(self)}: {self.shipping_method.name}/{self.destination}/{self.weight}/{self.rate}>"
