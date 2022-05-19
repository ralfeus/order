from sqlalchemy import Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app import db
from app.models import BaseModel

class DHLRate(db.Model, BaseModel):
    '''DHL rates by zone'''
    __tablename__ = 'dhl_rates'
    id = None
    when_changed = None
    when_created = None
    zone = Column(Integer, ForeignKey('dhl_zones.zone'), primary_key=True)
    weight = Column(Float, primary_key=True)
    rate = Column(Float)
    __countries = relationship('DHLCountry',
        primaryjoin="foreign(DHLRate.zone) == remote(DHLCountry.zone)",
        backref='rates')

    def to_dict(self):
        return {
            'zone': self.zone,
            'weight': self.weight,
            'rate': self.rate
        }
