from sqlalchemy import Column, ForeignKey, Integer, String

from app import db
from app.models import BaseModel

class WeightBasedRate(db.Model, BaseModel):
    __tablename__ = 'shipping_weight_based_rates'

    shipping_id = Column(Integer, ForeignKey('shipping.id'))
    minimum_weight = Column(Integer)
    maximum_weight = Column(Integer)
    destination = Column(String(2))
    cost_per_kg = Column(Integer)
    weight_step = Column(Integer)

    def to_dict(self):
        return {
            'id': self.id,
            'shipping_id': self.shipping_id,
            'minimum_weight': self.minimum_weight,
            'maximum_weight': self.maximum_weight,
            'cost_per_kg': self.cost_per_kg,
            'weight_step': self.weight_step
        }