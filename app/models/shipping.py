'''
Shipping method model
'''
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class Shipping(db.Model, BaseModel):
    '''
    Shipping method model
    '''
    __tablename__ = 'shipping'

    name = Column(String(16))
    rates = relationship('ShippingRate')
    