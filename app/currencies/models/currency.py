from sqlalchemy import Column, DateTime, Numeric, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class Currency(db.Model):
    __tablename__ = 'currencies'

    code = Column(String(3), primary_key=True, )
    name = Column(String(64))
    rate = Column(Numeric(scale=5))

    def __repr__(self):
        return "<Currency: {}>".format(self.code)

    def format(self, amount):
        return f'{amount} {self.code}'
        
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'rate': float(self.rate)
        }
