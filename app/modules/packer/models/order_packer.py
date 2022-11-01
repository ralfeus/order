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
    packer = Column(String(128), ForeignKey('packers.name'))

    def to_dict(self): 
        return {
            'id': self.order_id,
            'order_id': self.order_id,
            'packer': self.packer
        }

    def get_order_packer_for_sale_order(sender, details=False):
        order_packer = OrderPacker.query.get(sender.id)
        return order_packer.to_dict() if order_packer is not None else {}
