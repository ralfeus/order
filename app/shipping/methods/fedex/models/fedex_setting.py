from sqlalchemy import Column, ForeignKey, Integer, String

from app import db
from app.models.base import BaseModel

class FedexSetting (db.Model, BaseModel): # type: ignore
    __table_name__ = 'fedex_settings'
    
    id = None
    shipping_id = Column(Integer, ForeignKey('shipping.id'), primary_key=True)
    service_type = Column(String(64), default='')