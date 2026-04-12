"""Admin endpoint for manual DHL consignment creation."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.shipment import Shipment
from app.models.user import User
from app.schemas.shipment import ShipmentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/shipments', tags=['admin-consignments'])


class ConsignmentCreate(BaseModel):
    """Request body for manual consignment creation.

    ``force=True`` bypasses the confirmation guard when the shipment
    already has a tracking code or is in 'shipped' status.
    """
    force: bool = False


@router.post('/{shipment_id}/consignment', response_model=ShipmentResponse)
def create_consignment(
    shipment_id: int,
    body: ConsignmentCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Manually trigger consignment creation for a shipment.

    Returns 409 with a ``detail`` message when:
    - The shipment already has a tracking code, **or**
    - The shipment status is already 'shipped'

    …unless the caller passes ``force: true`` to confirm the re-creation.
    """
    shipment = db.query(Shipment).filter_by(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')

    # Guard: require explicit confirmation before overwriting an existing consignment
    if not body.force and (shipment.tracking_code or shipment.status == 'shipped'):
        reasons = []
        if shipment.tracking_code:
            reasons.append(f'already has tracking code "{shipment.tracking_code}"')
        if shipment.status == 'shipped':
            reasons.append('status is already "shipped"')
        raise HTTPException(
            status_code=409,
            detail=f'Shipment {", ".join(reasons)}. Pass force=true to overwrite.',
        )

    carrier = shipment.shipment_type
    if carrier is None:
        raise HTTPException(status_code=400, detail='Shipment has no carrier assigned')

    try:
        carrier.create_consignment(shipment, db)
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail=f'Carrier "{carrier.code}" does not support consignment creation',
        )
    except ValueError as exc:
        # Missing configuration
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        # DHL API errors
        logger.error('DHL API error for shipment %s: %s', shipment_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    db.commit()
    db.refresh(shipment)
    logger.info(
        'Consignment created for shipment %s: tracking=%s',
        shipment_id,
        shipment.tracking_code,
    )
    return shipment
