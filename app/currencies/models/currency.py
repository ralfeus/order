''' Currency '''
from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app import cache, db
from .currency_history_entry import CurrencyHistoryEntry

class Currency(db.Model): #type: ignore
    ''' Currency '''
    __tablename__ = 'currencies'

    code = Column(String(3), primary_key=True)
    name = Column(String(64))
    enabled = Column(Boolean)
    base = Column(Boolean)
    rate = Column(Numeric(scale=10))
    history = relationship("CurrencyHistoryEntry", lazy="dynamic")
    prefix = Column(String(1))
    suffix = Column(String(1))
    decimal_places = Column(Integer)

    @classmethod
    def get_base_currency(cls, tenant) -> 'Currency':
        ''' Get base currency '''
        if cache.get(f'{tenant}-base_currency') is None:
            base_currency = Currency.query.filter_by(base=True).first()
            cache.set(f'{tenant}-base_currency', base_currency, timeout=3600)
        return cache.get(f'{tenant}-base_currency')

    def __repr__(self):
        return "<Currency: {}>".format(self.code)

    def format(self, amount):
        if self.prefix is None and self.suffix is None:
            return f'{round(amount, self.decimal_places):,} {self.code}'.replace(',', ' ')
        return '{}{:,}{}'.format(
            self.prefix if self.prefix else "",
            round(amount, self.decimal_places),
            self.suffix if self.suffix else "").replace(',', ' ')

    def get_rate(self, date=datetime.now()) -> float:
        from app.currencies.models.currency_history_entry import CurrencyHistoryEntry
        latest_rate = self.history.filter(CurrencyHistoryEntry.when_created <= date) \
            .order_by(CurrencyHistoryEntry.when_created.desc()).first() #type: ignore
        if latest_rate is not None:
            return float(latest_rate.rate)
        return float(self.rate)
        
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'enabled': self.enabled,
            'rate': float(self.rate),
            'base': self.base,
        }