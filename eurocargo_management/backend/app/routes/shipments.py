from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.shipment import Shipment
from app.models.shipment_type import ShipmentType
from app.models.user import User
from app.schemas.shipment import ShipmentCreate, ShipmentCreatedResponse, ShipmentResponse

router = APIRouter(tags=['shipments'])


def _shipment_url(token: str) -> str:
    return f'{settings.base_url}/shipments/{token}'


def _to_response(shipment: Shipment) -> ShipmentResponse:
    data = ShipmentResponse.model_validate(shipment)
    data.shipment_url = _shipment_url(shipment.token)
    return data


@router.get('/shipments', response_model=list[ShipmentResponse])
def list_shipments(db: Session = Depends(get_db)):
    shipments = db.query(Shipment).all()
    return [_to_response(s) for s in shipments]


@router.post('/shipments', response_model=ShipmentCreatedResponse, status_code=201)
def create_shipment(payload: ShipmentCreate, db: Session = Depends(get_db)):
    shipment_type = db.query(ShipmentType).filter_by(
        code=payload.shipment_type_code, enabled=True
    ).first()
    if not shipment_type:
        raise HTTPException(status_code=422,
                            detail=f'Unknown or disabled shipment type: {payload.shipment_type_code}')

    existing = db.query(Shipment).filter_by(order_id=payload.order_id).first()
    if existing:
        raise HTTPException(status_code=409,
                            detail=f'Shipment for order {payload.order_id} already exists')

    shipment = Shipment(
        order_id=payload.order_id,
        customer_name=payload.customer_name,
        email=payload.email,
        address=payload.address,
        city=payload.city,
        country=payload.country,
        zip=payload.zip,
        phone=payload.phone,
        shipment_type_id=shipment_type.id,
        tracking_code=payload.tracking_code,
        amount_eur=payload.amount_eur,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return ShipmentCreatedResponse(
        id=shipment.id,
        token=shipment.token,
        shipment_url=_shipment_url(shipment.token),
    )


@router.get('/shipments/{token}', response_model=ShipmentResponse)
def get_shipment(
    token: str,
    user: Optional[str] = Query(default=None, description='OM username for auto-registration'),
    db: Session = Depends(get_db),
):
    shipment = db.query(Shipment).filter_by(token=token).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')

    if user:
        db_user = db.query(User).filter_by(username=user).first()
        if not db_user:
            db_user = User(username=user)
            db.add(db_user)
        if shipment.user_id is None:
            shipment.user_id = db_user.id if db_user.id else None
            db.flush()
            shipment.user_id = db_user.id
        db.commit()
        db.refresh(shipment)

    return _to_response(shipment)
