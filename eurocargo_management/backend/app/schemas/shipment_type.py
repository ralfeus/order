from pydantic import BaseModel


class ShipmentTypeResponse(BaseModel):
    id: int
    code: str
    name: str
    enabled: bool

    model_config = {'from_attributes': True}
