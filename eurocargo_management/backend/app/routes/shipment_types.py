from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.carrier import BaseCarrier
from app.schemas.shipment_type import ShipmentTypeResponse

router = APIRouter(tags=['shipment-types'])


@router.get('/shipment-types', response_model=list[ShipmentTypeResponse])
def list_shipment_types(db: Session = Depends(get_db)):
    return db.query(BaseCarrier).all()


@router.get('/shipment-types/{shipment_type_id}', response_model=ShipmentTypeResponse)
def get_shipment_type(shipment_type_id: int, db: Session = Depends(get_db)):
    shipment_type = db.get(BaseCarrier, shipment_type_id)
    if not shipment_type:
        raise HTTPException(status_code=404, detail='Shipment type not found')
    return shipment_type
