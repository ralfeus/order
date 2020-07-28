import enum
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class TransactionStatus(enum.Enum):
    pending = 1
    approved = 2
    rejected = 3
    cancelled = 4

class Transaction(db.Model):
    '''
    Customer wallet's transaction
    '''
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    currency_code = Column(String(3), ForeignKey('currencies.code'))
    currency = relationship('Currency')
    amount_orignal = Column(Float)
    amount_krw = Column(Integer)
    status = Column(Enum(TransactionStatus))
    created_at = Column(DateTime)
    changed_at = Column(DateTime)
    changed_by_id = Column(Integer, ForeignKey('users.id'))
    changed_by = relationship('User', foreign_keys=[changed_by_id])
