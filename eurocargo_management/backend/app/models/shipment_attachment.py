from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import relationship

from app.core.database import Base

ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class ShipmentAttachment(Base):
    """A file attached to a shipment (e.g. payment proof, invoice, packing list).

    Binary content is stored directly in PostgreSQL so deletions are
    transactional and there are no orphaned files on disk.
    """
    __tablename__ = 'shipment_attachments'

    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey('shipments.id'), nullable=False)
    filename = Column(String(256), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))

    shipment = relationship('Shipment', back_populates='attachments')
