''' Notification model '''
from sqlalchemy import Column, String, Text

from app import db
from app.models.base import BaseModel

class Notification(db.Model, BaseModel):
    ''' Notification model '''
    short_desc = Column(String(128))
    long_desc = Column(Text)
