from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import backref, relationship

from app import db
from app.models.base import BaseModel

class OrderPacker(db.Model, BaseModel):
    '''Association of the packer to order'''
    __tablename__ = 'order_packers'

    id = None
    order_id = Column(String(16), ForeignKey('orders.id'), primary_key=True)
    order = relationship('Order', foreign_keys=[order_id], backref='packer')
    packer = Column(String(128), ForeignKey('packers.name'), primary_key=True)

    def to_dict(self): 
        return {
            'order_id': self.order_id,
            'packer': self.packer
        }