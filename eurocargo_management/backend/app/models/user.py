from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(128), nullable=False, unique=True)
    password_hash = Column(String(128), nullable=True)
    role = Column(String(32), nullable=True)  # None = customer, 'admin' = admin
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    shipments = relationship('Shipment', back_populates='user')
