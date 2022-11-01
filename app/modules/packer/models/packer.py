from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.modules.packer.models.order_packer import OrderPacker

class Packer(db.Model, BaseModel):
    '''Represents a packer - a person packing a sale order'''
    __tablename__ = 'packers'

    id = None
    name = Column(String(128), primary_key=True)

    def to_dict(self):
        return {
            'name': self.name
        }