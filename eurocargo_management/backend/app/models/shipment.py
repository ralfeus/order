import secrets
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import Base


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class Shipment(Base):
    __tablename__ = 'shipments'

    id = Column(Integer, primary_key=True)
    token = Column(String(64), nullable=False, unique=True, default=_generate_token)
    order_id = Column(String(32), nullable=False, unique=True)
    customer_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False)
    address = Column(String(256), nullable=False)
    city = Column(String(128), nullable=False)
    country = Column(String(2), nullable=False)
    zip = Column(String(16), nullable=False)
    phone = Column(String(32), nullable=True)
    shipment_type_id = Column(Integer, ForeignKey('shipment_types.id'), nullable=False)
    tracking_code = Column(String(64), nullable=True)
    amount_eur = Column(Numeric(10, 2), nullable=False)
    status = Column(String(16), nullable=False, default='pending')
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    shipment_type = relationship('ShipmentType', back_populates='shipments')
    payments = relationship('Payment', back_populates='shipment')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user = relationship('User', back_populates='shipments')
