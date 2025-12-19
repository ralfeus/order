'''
Country model
'''
from sqlalchemy import Column, Integer, String # type: ignore

from app import cache, db

class Country(db.Model): # type: ignore
    '''
    Country model
    '''
    __tablename__ = 'countries'

    id = Column(String(2), primary_key=True)
    name = Column(String(64))
    capital: str = Column(String(64))
    first_zip = Column(String(9))
    locale = Column(String(5))
    currency_code = Column(String(3))
    sort_order = Column(Integer, default=999)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'capital': self.capital,
            'first_zip': self.first_zip,
            'sort_order': self.sort_order,
            'currency_code': self.currency_code,
            'locale': self.locale
        }

    @classmethod
    def get_base_country(cls, tenant) -> 'Country':
        ''' Get base country '''
        if cache.get(f'{tenant}-base_country') is None:
            from app.currencies.models.currency import Currency
            base_country = Country.query.filter_by(
                currency_code=Currency.get_base_currency(tenant).code).first()
            cache.set(f'{tenant}-base_country', base_country, timeout=3600)
        return cache.get(f'{tenant}-base_country')
