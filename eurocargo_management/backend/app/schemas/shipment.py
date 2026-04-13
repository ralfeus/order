from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr

from .attachment import AttachmentMeta
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
    shipment_type_code: Optional[str] = None  # chosen later at payment time
    weight_kg: Decimal
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    tracking_code: Optional[str] = None


class ShipmentTypeUpdate(BaseModel):
    shipment_type_code: str


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
    shipment_type: Optional[ShipmentTypeResponse] = None
    weight_kg: Decimal
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    tracking_code: Optional[str]
    amount_eur: Optional[Decimal] = None
    status: str
    paid: bool = False
    created_at: datetime
    updated_at: datetime
    shipment_url: str = ''  # computed after model_validate
    attachments: list[AttachmentMeta] = []

    model_config = {'from_attributes': True}


class ShipmentCreatedResponse(BaseModel):
    id: int
    token: str
    shipment_url: str


class CostResponse(BaseModel):
    cost_eur: Decimal
