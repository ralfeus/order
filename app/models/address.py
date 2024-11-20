from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.models.country import Country

class Address(db.Model, BaseModel):  # type: ignore
    __tablename__ = 'addresses'
    
    name: str = Column(String(32)) # type: ignore
    zip: str = Column(String(5)) # type: ignore
    address_1: str = Column(String(64)) # type: ignore
    address_2: str = Column(String(64)) # type: ignore
    address_1_eng: str = Column(String(65)) # type: ignore
    address_2_eng: str = Column(String(65)) # type: ignore
    city_eng: str = Column(String(65)) # type: ignore
    country_id: str = Column(String(2), ForeignKey('countries.id')) # type: ignore
    country: Country = relationship(Country, foreign_keys=[country_id]) # type: ignore
    delivery_comment: str = Column(Text) # type: ignore
    user_created: bool = Column(Boolean, default=False) # type: ignore

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