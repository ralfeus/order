'''Setting model'''
from sqlalchemy import Column, String

from app import db
from app.models.base import BaseModel

class Setting(db.Model, BaseModel):
    '''Represents setting'''
    __tablename__ = 'settings'

    id = None # The 'key' is a primary key. So no will be here
    key = Column(String(64), primary_key=True)
    value = Column(String(128))
    default_value = Column(String(128))
    description = Column(String(256))

    @classmethod
    def get(cls, setting_name):
        '''Gets setting's value or None if setting doesn't exist'''
        setting = Setting.query.get(setting_name)
        if setting is not None:
            return setting.value
        return None

    @classmethod
    def __getitem__(cls, setting_name):
        return cls.get(setting_name)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'default_value': self.default_value,
            'description': self.description,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }