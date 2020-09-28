from sqlalchemy import Column, String
from app import db
from app.models.base import BaseModel

class PaymentMethod(db.Model, BaseModel):
    __tablename__ = 'payment_methods'

    name = Column(String(16))

    def __repr__(self):
        return f"<PaymentMethod: {self.id} - {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }