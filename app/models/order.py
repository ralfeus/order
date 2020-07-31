'''
Order model
'''
from functools import reduce

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class Order(db.Model):
    ''' System's order '''
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    invoice_id = Column(String(16), ForeignKey('invoices.id'))
    invoice = relationship('Invoice', foreign_keys=[invoice_id])
    name = Column(String(16))
    address = Column(String(64))
    country = Column(String(128))
    phone = Column(String(32))
    comment = Column(String(128))
    when_created = Column(DateTime)
    order_products = relationship('OrderProduct', backref='order', lazy='dynamic')

    def __repr__(self):
        return "<Order: {}>".format(self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'user': self.user.username if self.user else None,
            'customer': self.name,
            'total': reduce(lambda self, op: op.price * op.quantity, self.order_products, 0),
            'when_created': self.when_created
        }
