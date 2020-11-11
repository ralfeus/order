from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel

class PaymentMethod(db.Model, BaseModel):
    __tablename__ = 'payment_methods'

    name = Column(String(16))
    payee_id = Column(Integer, ForeignKey('companies.id'))
    payee = relationship('Company', foreign_keys=[payee_id])

    def __repr__(self):
        return f"<PaymentMethod: {self.id} - {self.name}>"

    def __str__(self):
        return str(self.name)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'payee_id': self.payee_id,
            # 'payee': self.payee.name if self.payee else None
        }