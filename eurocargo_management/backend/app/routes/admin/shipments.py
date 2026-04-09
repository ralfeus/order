"""Admin shipment management endpoints."""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.shipment import Shipment
from app.models.user import User
from app.schemas.shipment import ShipmentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/shipments', tags=['admin-shipments'])

ALLOWED_STATUSES = {'pending', 'paid', 'shipped'}


class StatusUpdate(BaseModel):
    status: Literal['pending', 'paid', 'shipped']


class TrackingUpdate(BaseModel):
    tracking_code: Optional[str] = None


@router.get('', response_model=list[ShipmentResponse])
def list_all_shipments(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return all shipments ordered by creation date (newest first)."""
    shipments = (
        db.query(Shipment)
        .order_by(Shipment.created_at.desc())
        .all()
    )
    return shipments


@router.patch('/{shipment_id}/status', response_model=ShipmentResponse)
def update_status(
    shipment_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Change the status of a shipment."""
    shipment = db.query(Shipment).filter_by(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    shipment.status = body.status
    db.commit()
    db.refresh(shipment)
    logger.info('Shipment %s status changed to %s by admin', shipment_id, body.status)
    return shipment


@router.patch('/{shipment_id}/tracking', response_model=ShipmentResponse)
def update_tracking(
    shipment_id: int,
    body: TrackingUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Set or clear the tracking code of a shipment."""
    shipment = db.query(Shipment).filter_by(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    shipment.tracking_code = body.tracking_code
    db.commit()
    db.refresh(shipment)
    logger.info('Shipment %s tracking_code set to %r by admin', shipment_id, body.tracking_code)
    return shipment
