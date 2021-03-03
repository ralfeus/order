from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.address import Address
from app.models.base import BaseModel

class Company(db.Model, BaseModel):
    __tablename__ = 'companies'

    name = Column(String(32))
    tax_id_1 = Column(String(3))
    tax_id_2 = Column(String(2))
    tax_id_3 = Column(String(5))
    phone = Column(String(13))
    address_id = Column(Integer, ForeignKey('addresses.id'))
    address = relationship('Address', foreign_keys=[address_id])
    bank_id = Column(String(2))

    def __repr__(self):
        return f"<Company {self.id}: {self.name}>"

    @property
    def tax_id(self):
        return (self.tax_id_1, self.tax_id_2, self.tax_id_3)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'tax_id': f"{self.tax_id_1}-{self.tax_id_2}-{self.tax_id_3}",
            'phone': self.phone,
            'address': self.address.to_dict()
        }
