''' Currency rate history entry '''
from sqlalchemy import Column, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from app import db
from app.models.base import BaseModel

class CurrencyHistoryEntry(BaseModel, db.Model):
    ''' Currency rate history entry '''
    __tablename__ = 'currency_history'

    code = Column(String(3), ForeignKey('currencies.code'))
    rate = Column(Numeric(scale=5))
