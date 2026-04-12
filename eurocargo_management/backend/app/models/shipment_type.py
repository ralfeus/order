from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class ShipmentType(Base):
    __tablename__ = 'shipment_types'

    id = Column(Integer, primary_key=True)
    code = Column(String(16), nullable=False, unique=True)
    name = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    shipments = relationship('Shipment', back_populates='shipment_type')
