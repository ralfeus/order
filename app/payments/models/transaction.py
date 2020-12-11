'''
User's financial transaction of any kind
'''
import logging

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.models import User

class Transaction(db.Model, BaseModel):
    __tablename__ = 'transactions'

    customer_id = Column(Integer(), ForeignKey('users.id'))
    customer = relationship('User', foreign_keys=[customer_id])
    amount = Column(Integer())
    user_id = Column(Integer(), ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])

    def __init__(self, amount, customer_id=None, customer=None, user_id=None,
                 user=None, **kwargs):
        if not customer:
            customer = User.query.get(customer_id)
        if not user:
            user = User.query.get(user_id)
        kwargs['amount'] = amount
        kwargs['customer'] = customer
        kwargs['user'] = user
        super().__init__(**kwargs)

        self.update_customer_balance()
    
    def update_customer_balance(self):
        self.customer.balance += self.amount
        logging.getLogger().info(
            'Changed balance of customer <%s> on %d. New balance is %d',
            self.customer.username, self.amount, self.customer.balance)
