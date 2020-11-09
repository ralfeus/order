'''
Abscract base model
'''
from sqlalchemy import Column, DateTime, Integer

class BaseModel:
    '''
    Base model
    '''
    id = Column(Integer, primary_key=True)
    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)

    # @classmethod
    # def from_dict(cls, attr):
    #     for attribute in cls.__dict__.items():
    #         if attribute[0] == attr:
    #             return attribute[1]
    #     return None