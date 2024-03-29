from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean

from app import db
from app.models.address import Address
from app.models.base import BaseModel

class Company(db.Model, BaseModel): #type: ignore
    __tablename__ = 'companies'

    name = Column(String(32))
    contact_person = Column(String(64))
    tax_id_1 = Column(String(3))
    tax_id_2 = Column(String(2))
    tax_id_3 = Column(String(5))
    phone = Column(String(13))
    address_id = Column(Integer, ForeignKey('addresses.id'))
    address:Address = relationship(Address, foreign_keys=[address_id])
    tax_simplified = Column(Boolean, default=True)
    tax_phone = Column(String(13))
    tax_address_id = Column(Integer, ForeignKey('addresses.id'))
    tax_address = relationship(Address, foreign_keys=[tax_address_id])
    business_type = Column(String(64))
    business_category = Column(String(64))
    email = Column(String(64))
    bank_id = Column(String(2))
    default = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Company {self.id}: {self.name}>"

    def __str__(self):
        return str(self.name)

    @property
    def tax_id(self):
        return (self.tax_id_1, self.tax_id_2, self.tax_id_3)
   
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'tax_id': f"{self.tax_id_1}-{self.tax_id_2}-{self.tax_id_3}",
            'phone': self.phone,
            'address': self.address.to_dict(),
            'bank_id' : self.bank_id,
            'contact_person' : self.contact_person,
            'default': self.default,
            'tax_simplified': self.tax_simplified,
            'tax_address': self.tax_address.to_dict() if self.tax_address else None,
            'tax_phone': self.tax_phone,
            'email': self.email,
            'business_type': self.business_type,
            'business_category': self.business_category,
            'enabled': self.enabled
        }
