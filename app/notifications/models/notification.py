''' Notification model '''
from sqlalchemy import Column, String, Text

from app import db
from app.models.base import BaseModel

class Notification(db.Model, BaseModel):
    ''' Notification model '''
    __tablename__ = 'notifications'

    short_desc = Column(String(128))
    long_desc = Column(Text)

    def to_dict(self, details=False):
        return {
            'id': self.id,
            'short_desc': self.short_desc,
            'long_desc': self.long_desc,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
