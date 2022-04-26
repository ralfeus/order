from sqlalchemy import Column, ForeignKey, Integer, String

from app import db
from app.models import BaseModel

class WeightBasedRate(db.Model, BaseModel):
    __tablename__ = 'shipping_weight_based_rates'

    id = None
    shipping_id = Column(Integer, ForeignKey('shipping.id'), primary_key=True)
    destination = Column(String(2), primary_key=True)
    minimum_weight = Column(Integer)
    maximum_weight = Column(Integer)
    cost_per_kg = Column(Integer)
    weight_step = Column(Integer)

    def to_dict(self):
        return {
            'id': f'{self.shipping_id}-{self.destination}',
            'shipping_id': self.shipping_id,
            'destination': self.destination,
            'minimum_weight': self.minimum_weight,
            'maximum_weight': self.maximum_weight,
            'cost_per_kg': self.cost_per_kg,
            'weight_step': self.weight_step
        }