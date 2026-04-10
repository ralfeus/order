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

SHIPMENT_STATUSES = ('incoming', 'at_warehouse', 'customs_cleared', 'shipped')


class StatusUpdate(BaseModel):
    status: Literal['incoming', 'at_warehouse', 'customs_cleared', 'shipped']


class PaidUpdate(BaseModel):
    paid: bool


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
    """Change the logistics status of a shipment.

    When status changes to 'shipped', automatically attempts to create a
    carrier consignment (e.g. DHL label). Failures are logged but do NOT
    prevent the status update from succeeding.
    """
    shipment = db.query(Shipment).filter_by(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')

    previous_status = shipment.status
    shipment.status = body.status

    # Auto-create consignment when transitioning to 'shipped'
    if body.status == 'shipped' and previous_status != 'shipped':
        carrier = shipment.shipment_type
        if carrier is not None:
            try:
                carrier.create_consignment(shipment, db)
                logger.info(
                    'Auto-created consignment for shipment %s via carrier %s',
                    shipment_id,
                    carrier.code,
                )
            except NotImplementedError:
                logger.debug(
                    'Carrier %s does not support auto-consignment for shipment %s',
                    carrier.code,
                    shipment_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    'Auto-consignment failed for shipment %s (carrier %s): %s',
                    shipment_id,
                    carrier.code,
                    exc,
                )

    db.commit()
    db.refresh(shipment)
    logger.info('Shipment %s status changed to %s by admin', shipment_id, body.status)
    return shipment


@router.patch('/{shipment_id}/paid', response_model=ShipmentResponse)
def update_paid(
    shipment_id: int,
    body: PaidUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Toggle the paid flag of a shipment."""
    shipment = db.query(Shipment).filter_by(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    shipment.paid = body.paid
    db.commit()
    db.refresh(shipment)
    logger.info('Shipment %s paid set to %s by admin', shipment_id, body.paid)
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
