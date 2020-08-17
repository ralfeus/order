'''
Country model
'''
from sqlalchemy import Column, String

from app import db

class Country(db.Model):
    '''
    Country model
    '''
    __tablename__ = 'countries'

    id = Column(String(2), primary_key=True)
    name = Column(String(64))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }