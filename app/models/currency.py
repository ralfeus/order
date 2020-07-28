from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class Currency(db.Model):
    __tablename__ = 'currencies'

    code = Column(String(3), primary_key=True)
    name = Column(String(64))
    rate = Column(Float(5))

    def __repr__(self):
        return "<Currency: {}>".format(self.code)

    def format(self, amount):
        return f"{amount} {self.code}"