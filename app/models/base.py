'''
Abscract base model
'''
from sqlalchemy import Column, DateTime

class BaseModel:
    '''
    Base model
    '''
    id = Column(Integer, primary_key=True)
    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)