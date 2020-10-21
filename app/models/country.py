'''
Country model
'''
from sqlalchemy import Column, Integer, String

from app import db

class Country(db.Model):
    '''
    Country model
    '''
    __tablename__ = 'countries'

    id = Column(String(2), primary_key=True)
    name = Column(String(64))
    sort_order = Column(Integer, default=999)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'sort_order': self.sort_order
        }