'''Add on to Subcustomer model storing their PV stats'''
from sqlalchemy import Boolean, Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel

class PVStat(BaseModel, db.Model):
    '''Represents add on to subcustomer storing its PV stats'''
    __tablename__ = 'pv_stats_permissions'

    node_id = Column(String(8))
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    allowed = Column(Boolean, default=False)
    is_being_updated = Column(Boolean, default=False)

    def to_dict(self):
        '''JSON representation'''
        return {
            'id': self.id,
            'node_id': self.node_id,
            'node_name': None,
            'user_id': self.user_id,
            'user_name': self.user.username,
            'allowed': self.allowed,
            'network_pv': None,
            'left_pv': None,
            'right_pv': None,
            'is_being_updated': self.is_being_updated,
            'when_updated': None,
            'when_created': self.when_created,
            'when_changed': self.when_changed
        }
