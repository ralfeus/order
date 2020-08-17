'''
Shipping method model
'''
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel

class Shipping(db.Model, BaseModel):
    '''
    Shipping method model
    '''
    __tablename__ = 'shipping'

    name = Column(String(16))
    rates = relationship('ShippingRate')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }
