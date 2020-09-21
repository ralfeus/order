'''
Suborder model
Part of the order for single subcustomer
'''
from datetime import datetime
from functools import reduce

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel

class Suborder(db.Model, BaseModel):
    ''' Suborder '''
    __tablename__ = 'suborders'

    subcustomer_id = Column(Integer, ForeignKey('subcustomers.id'))
    subcustomer = relationship("Subcustomer", foreign_keys=[subcustomer_id])
    order_id = Column(String(16), ForeignKey('orders.id'))
    order = relationship('Order', foreign_keys=[order_id])
    buyout_date = Column(DateTime, index=True)
    #subtotal_krw = Column(Integer(), default=0)
    #subtotal_rur = Column(Numeric(10, 2), default=0)
    #subtotal_usd = Column(Numeric(10, 2), default=0)
    order_products = relationship('OrderProduct', lazy='dynamic')

    @property
    def total_weight(self):
        return reduce(lambda acc, op: acc + op.product.weight * op.quantity, self.order_products, 0)

    @property
    def total_krw(self):
        return reduce(lambda acc, op: acc + op.price * op.quantity, self.order_products, 0)

    def __repr__(self):
        return "<Suborder: {} Order: {}>".format(self.id, self.order_id)

    def to_dict(self):
#        if not self.total_krw:
#            self.total_krw = reduce(lambda acc, op: acc + op.price * op.quantity, self.order_products, 0)
#        if not self.total_rur:
#            self.total_rur = self.total_krw * Currency.query.get('RUR').rate
#        if not self.total_usd:
#            self.total_usd = self.total_krw * Currency.query.get('USD').rate
        return {
            'id': self.id,
            'order_id': self.order_id,
            'subcustomer': self.subcustomer.name if self.subcustomer else None,
            'buyout_date': self.buyout_date.strftime('%Y-%m-%d') if self.buyout_date else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else None
        }

