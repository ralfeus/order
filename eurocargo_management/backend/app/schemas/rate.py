from decimal import Decimal
from pydantic import BaseModel


class RateEntryResponse(BaseModel):
    id: int
    shipment_type_code: str
    country: str
    max_weight_kg: Decimal
    cost: Decimal

    model_config = {'from_attributes': True}


class CarrierRatesResponse(BaseModel):
    code: str
    name: str
    multiplier: Decimal
    entries: list[RateEntryResponse]

    model_config = {'from_attributes': True}


class MultiplierUpdate(BaseModel):
    multiplier: Decimal

    def validate_positive(self):
        if self.multiplier <= 0:
            raise ValueError('Multiplier must be a positive number')
