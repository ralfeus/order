'''
User's financial transaction of any kind
'''
import logging

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.users.models.user import User

class Transaction(BaseModel, db.Model):
    __tablename__ = 'transactions'

    customer_id = Column(Integer(), ForeignKey('users.id'))
    customer = relationship('User', foreign_keys=[customer_id])
    customer_balance = Column(Integer())
    amount = Column(Integer())
    user_id = Column(Integer(), ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    order = relationship('Order', uselist=False)
    payment = relationship('Payment', uselist=False)

    def __init__(self, amount, customer_id=None, customer=None, user_id=None,
                 user=None, **kwargs):
        if not customer:
            customer = User.query.get(customer_id)
        if not user:
            user = User.query.get(user_id)
        self.__update_customer_balance(customer, amount)
        kwargs['amount'] = amount
        kwargs['customer'] = customer
        kwargs['user'] = user
        kwargs['customer_balance'] = customer.balance
        super().__init__(**kwargs)

    
    def __update_customer_balance(self, customer, amount):
        customer.balance += amount
        logging.getLogger().info(
            'Changed balance of customer <%s> on %d. New balance is %d',
            customer.username, amount, customer.balance)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order.id if self.order \
                else [o.id for o in self.payment.orders] if self.payment \
                else None,
            'customer': self.customer.username,
            'amount': self.amount,
            'customer_balance': self.customer_balance,
            'created_by': self.user.username,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
