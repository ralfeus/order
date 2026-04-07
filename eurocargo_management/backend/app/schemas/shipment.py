from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr

from .shipment_type import ShipmentTypeResponse


class ShipmentCreate(BaseModel):
    order_id: str
    customer_name: str
    email: EmailStr
    address: str
    city: str
    country: str
    zip: str
    phone: Optional[str] = None
    shipment_type_code: str
    tracking_code: Optional[str] = None
    amount_eur: Decimal


class ShipmentResponse(BaseModel):
    id: int
    token: str
    order_id: str
    customer_name: str
    email: str
    address: str
    city: str
    country: str
    zip: str
    phone: Optional[str]
    shipment_type: ShipmentTypeResponse
    tracking_code: Optional[str]
    amount_eur: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    shipment_url: str = ''  # computed after model_validate

    model_config = {'from_attributes': True}


class ShipmentCreatedResponse(BaseModel):
    id: int
    token: str
    shipment_url: str
