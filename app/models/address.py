from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.models.country import Country

class Address(db.Model, BaseModel):
    __tablename__ = 'addresses'
    
    name = Column(String(32))
    zip = Column(String(5))
    address_1 = Column(String(64))
    address_2 = Column(String(64))
    address_1_eng = Column(String(65))
    address_2_eng = Column(String(65))
    city_eng = Column(String(65))
    country_id = Column(String(2), ForeignKey('countries.id'))
    country = relationship(Country, foreign_keys=[country_id])
    delivery_comment = Column(Text)
    user_created = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Address {self.id}: {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'zip': self.zip,
            'address_1': self.address_1,
            'address_2': self.address_2,
            'address_1_eng': self.address_1_eng,
            'address_2_eng': self.address_2_eng,
            'city_eng': self.city_eng,
            'delivery_comment': self.delivery_comment
        }
