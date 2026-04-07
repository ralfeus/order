from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey('shipments.id'), nullable=False)
    revolut_order_id = Column(String(64), nullable=True, unique=True)
    method = Column(String(16), nullable=True)  # 'card' or 'sepa'
    status = Column(String(16), nullable=False, default='pending')
    amount_eur = Column(Numeric(10, 2), nullable=False)
    checkout_url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    shipment = relationship('Shipment', back_populates='payments')
