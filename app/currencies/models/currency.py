''' Currency '''
from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app import db
from .currency_history_entry import CurrencyHistoryEntry

class Currency(db.Model):
    ''' Currency '''
    __tablename__ = 'currencies'

    code = Column(String(3), primary_key=True)
    name = Column(String(64))
    enabled = Column(Boolean)
    rate = Column(Numeric(scale=10))
    history = relationship("CurrencyHistoryEntry", lazy="dynamic")
    prefix = Column(String(1))
    suffix = Column(String(1))
    decimal_places = Column(Integer)

    def __repr__(self):
        return "<Currency: {}>".format(self.code)

    def format(self, amount):
        if self.prefix is None and self.suffix is None:
            return f'{round(amount, self.decimal_places):,} {self.code}'.replace(',', ' ')
        return '{}{:,}{}'.format(
            self.prefix if self.prefix else "",
            round(amount, self.decimal_places),
            self.suffix if self.suffix else "").replace(',', ' ')

    def get_rate(self, date=datetime.now()):
        from app.currencies.models.currency_history_entry import CurrencyHistoryEntry
        latest_rate = self.history.filter(CurrencyHistoryEntry.when_created <= date) \
            .order_by(CurrencyHistoryEntry.when_created.desc()).first()
        if latest_rate is not None:
            return latest_rate.rate
        return self.rate
        
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'enabled': self.enabled,
            'rate': float(self.rate)
        }
