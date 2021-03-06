from sqlalchemy import Column, String

from app import db
from app.models.base import BaseModel

class Address(db.Model, BaseModel):
    __tablename__ = 'addresses'
    
    name = Column(String(32))
    zip = Column(String(5))
    address_1 = Column(String(64))
    address_2 = Column(String(64))

    def __repr__(self):
        return f"<Address {self.id}: {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'zip': self.zip,
            'address_1': self.address_1,
            'address_2': self.address_2
        }