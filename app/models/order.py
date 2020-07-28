'''
Order model
'''
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class Order(db.Model):
    ''' System's order '''
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    name = Column(String(16))
    address = Column(String(64))
    country = Column(String(128))
    phone = Column(String(32))
    comment = Column(String(128))
    when_created = Column(DateTime)
    order_products = relationship('OrderProduct', backref='order', lazy='dynamic')

    def __repr__(self):
        return "<Order: {}>".format(self.id)
