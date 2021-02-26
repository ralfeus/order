''' Files model'''
from sqlalchemy import Column, String

from app import db
from .base import BaseModel

class File(BaseModel, db.Model):
    '''Files model'''
    __tablename__ = 'files'
    file_name = Column(String(128))
    path = Column(String(128))

    def to_dict(self):
        return {
            'file_name': self.file_name,
            'path': self.path
        }