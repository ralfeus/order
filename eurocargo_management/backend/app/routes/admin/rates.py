"""Admin rate table and carrier multiplier endpoints."""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.carrier import BaseCarrier
from app.models.shipping_rate import ShippingRateEntry
from app.models.user import User
from app.schemas.rate import CarrierRatesResponse, RateEntryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/rates', tags=['admin-rates'])


class MultiplierUpdate(BaseModel):
    multiplier: Decimal

    @field_validator('multiplier')
    @classmethod
    def must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('Multiplier must be a positive number')
        return v


@router.get('', response_model=list[CarrierRatesResponse])
def list_carrier_rates(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return all carriers with their rate entries."""
    carriers = db.query(BaseCarrier).order_by(BaseCarrier.code).all()
    return [_build_response(c, db) for c in carriers]


@router.get('/{carrier_code}', response_model=CarrierRatesResponse)
def get_carrier_rates(
    carrier_code: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return rate entries for a specific carrier."""
    carrier = db.query(BaseCarrier).filter_by(code=carrier_code).first()
    if not carrier:
        raise HTTPException(status_code=404, detail=f'Carrier {carrier_code!r} not found')
    return _build_response(carrier, db)


@router.patch('/{carrier_code}/multiplier', response_model=CarrierRatesResponse)
def update_multiplier(
    carrier_code: str,
    body: MultiplierUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update the rate multiplier for a carrier."""
    carrier = db.query(BaseCarrier).filter_by(code=carrier_code).first()
    if not carrier:
        raise HTTPException(status_code=404, detail=f'Carrier {carrier_code!r} not found')
    carrier.multiplier = body.multiplier
    db.commit()
    db.refresh(carrier)
    logger.info('Carrier %s multiplier set to %s', carrier_code, body.multiplier)
    return _build_response(carrier, db)


def _build_response(carrier: BaseCarrier, db: Session) -> CarrierRatesResponse:
    entries = (
        db.query(ShippingRateEntry)
        .filter_by(shipment_type_code=carrier.code)
        .order_by(ShippingRateEntry.country, ShippingRateEntry.max_weight_kg)
        .all()
    )
    return CarrierRatesResponse(
        code=carrier.code,
        name=carrier.name,
        multiplier=carrier.multiplier,
        entries=[RateEntryResponse.model_validate(e) for e in entries],
    )
