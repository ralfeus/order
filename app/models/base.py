'''
Abscract base model
'''
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db

class BaseModel:
    '''
    Base model
    '''
    id = Column(Integer, primary_key=True)
    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)

    def __init__(self, **kwargs):
        self.when_created = datetime.now()
        # Set all attributes passed
        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])

    @classmethod
    def get_filter(cls, base_filter, column, filter_value):
        raise NotImplementedError(f'get_filter() is not implemented for {cls}')

    def delete(self):
        db.session.delete(self)


    # @classmethod
    # def from_dict(cls, attr):
    #     for attribute in cls.__dict__.items():
    #         if attribute[0] == attr:
    #             return attribute[1]
    #     return None