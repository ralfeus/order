'''
Subcustomer model
'''
from datetime import datetime
from decimal import Decimal
from functools import reduce

from sqlalchemy import Column, DateTime, Numeric, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, validates
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.models.base import BaseModel

class Subcustomer(db.Model, BaseModel):
    ''' Subcustomer '''
    __tablename__ = 'subcustomers'

    name = Column(String(128))
    username = Column(String(16))
    password = Column(String(16))
    suborders = relationship("Suborder", lazy='dynamic')

    def __repr__(self):
        return "<Subcustomer: {} {}>".format(self.id, self.name)

    @validates('username', 'password')
    def validate_creds(self, key, value):
        if len(value) > 16:
            raise ValueError(f'The <{key}> length should be up to 16 characters')
        return value

    def get_purchase_orders(self):
        return map(lambda s: s.get_purchase_order(), self.suborders)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'password': self.password,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else None
        }

