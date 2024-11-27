import re

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel


class PaymentMethod(db.Model, BaseModel): #type: ignore
    __tablename__ = 'payment_methods'
    discriminator = Column(String(50))
    __mapper_args__ = {
        'polymorphic_on': discriminator, 
        'polymorphic_identity': 'default'
    }

    name = Column(String(32))
    payee_id = Column(Integer, ForeignKey('companies.id'))
    payee = relationship('Company', foreign_keys=[payee_id])
    instructions = Column(Text)
    enabled = Column(Boolean)

    def __repr__(self):
        return f"<PaymentMethod: {self.id} - {self.name}>"

    def __str__(self):
        return str(self.name)

    def validate_sender_name(self, name):
        if re.match(r'^[a-zA-Z ]+$', name) is None:
            raise Exception('Must contain only latin letters')

    def execute_payment(self, _payment):
        '''Executes automated payment.
        In general case just does nothing. Specifics are implemented in descendants'''
        return None

    def to_dict(self):
        '''Returns object's representation as a map'''
        return {
            'id': self.id,
            'name': self.name,
            'payee_id': self.payee_id,
            'payee': self.payee.name if self.payee else None,
            'instructions': self.instructions,
            'enabled': self.enabled
        }