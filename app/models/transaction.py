from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime)
    currency_code = Column(Integer, ForeignKey('currencies.code'))
    currency = relationship('Currency')
    amount_krw = Column(Integer)
    status = Column(String(16))
