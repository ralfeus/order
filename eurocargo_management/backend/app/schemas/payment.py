from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    method: str  # 'card' or 'sepa'


class PaymentResponse(BaseModel):
    id: int
    revolut_order_id: Optional[str]
    method: Optional[str]
    status: str
    amount_eur: Decimal
    checkout_url: Optional[str]
    created_at: datetime

    model_config = {'from_attributes': True}
