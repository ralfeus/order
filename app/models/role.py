'''
User model
'''
from flask_security import RoleMixin
from sqlalchemy import Column, String

from app import db
from app.models.base import BaseModel

class Role(db.Model, BaseModel, RoleMixin):
    '''
    Represents site's role
    '''
    __tablename__ = 'roles'

    # Identification
    name = Column(String(32), unique=True, nullable=False)
