from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models import BaseModel

class DHLCountry(db.Model, BaseModel):
    '''Maps countries to zone'''
    __tablename__ = 'dhl_countries'

    id = None
    when_created = None
    when_changed = None
    country_id = Column(String(2), ForeignKey('countries.id'), primary_key=True)
    zone = Column(Integer, ForeignKey('dhl_zones.zone'))
