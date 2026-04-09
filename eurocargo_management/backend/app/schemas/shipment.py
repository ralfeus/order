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
    shipment_type_code: str
    weight_kg: Decimal
    tracking_code: Optional[str] = None


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
    weight_kg: Decimal
    tracking_code: Optional[str]
    amount_eur: Optional[Decimal] = None
    status: str
    created_at: datetime
    updated_at: datetime
    shipment_url: str = ''  # computed after model_validate
    attachments: list[AttachmentMeta] = []

    model_config = {'from_attributes': True}


class ShipmentCreatedResponse(BaseModel):
    id: int
    token: str
    shipment_url: str
