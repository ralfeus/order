'''
Country model
'''
from sqlalchemy import Column, Integer, String # type: ignore

from app import db

class Country(db.Model): # type: ignore
    '''
    Country model
    '''
    __tablename__ = 'countries'

    id = Column(String(2), primary_key=True)
    name = Column(String(64))
    capital: str = Column(String(64))
    first_zip = Column(String(9))
    sort_order = Column(Integer, default=999)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'capital': self.capital,
            'first_zip': self.first_zip,
            'sort_order': self.sort_order
        }