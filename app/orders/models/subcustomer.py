'''Subcustomer model'''
from sqlalchemy import Column, String, Boolean, or_
from sqlalchemy.orm import relationship, validates

from app import db
from app.models.base import BaseModel
from app.network.models.node import Node

class Subcustomer(db.Model, BaseModel):
    ''' Subcustomer '''
    __tablename__ = 'subcustomers'

    name = Column(String(128))
    username = Column(String(16))
    password = Column(String(32))
    in_network = Column(Boolean())
    center_code = Column(String(8))
    # suborders = relationship("Suborder", lazy='dynamic')

    def __repr__(self):
        return "<Subcustomer: {} {}>".format(self.id, self.name)

    @validates('username')
    def validate_username(self, key, value):
        '''Validates username value'''
        if len(value) > 16:
            raise ValueError(f'The <{key}> length should be up to 16 characters')
        return value

    @validates('password')
    def validate_password(self, key, value):
        '''Validates password value'''
        if len(value) > 32:
            raise ValueError(f'The <{key}> length should be up to 32 characters')
        return value

    @classmethod
    def get_filter(cls, base_filter, column=None, filter_value=None):
        part_filter = f'%{filter_value}%'
        filter_values = filter_value.split(',')
        if column is None:
            return \
                base_filter.filter(or_(
                    Subcustomer.name.like(part_filter),
                    Subcustomer.username.like(part_filter)
                ))

    def is_internal(self):
        '''Defines whether subcustomer belongs to tenant's network'''
        if self.in_network is None:
            return Node.query.get(self.username) is not None
        return self.in_network

    # def get_purchase_orders(self):
    #     '''Returns all purchase orders of the subcustomer'''
    #     return map(lambda s: s.get_purchase_order(), self.suborders)

    def to_dict(self):
        '''Returns dict representation of the object'''
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'password': self.password,
            'center_code': self.center_code,
            'in_network': self.in_network,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
