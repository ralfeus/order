from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models import BaseModel

class DHLZone(db.Model, BaseModel):
    '''Maps countries to zone'''
    __tablename__ = 'dhl_zones'

    id = None
    when_created = None
    when_changed = None
    zone = Column(Integer, primary_key=True)
