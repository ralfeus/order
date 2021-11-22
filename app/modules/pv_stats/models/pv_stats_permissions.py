'''Add on to Subcustomer model storing their PV stats'''
from sqlalchemy import Boolean, Column, Integer, ForeignKey, String

from app import db
from app.models.base import BaseModel

class PVStatsPermissions(BaseModel, db.Model):
    '''Represents add on to subcustomer storing its PV stats'''
    __tablename__ = 'pv_stats_permissions'

    node_id = Column(String(8))
    user_id = Column(Integer, ForeignKey('users.id'))
    allowed = Column(Boolean, default=False)

    def to_dict(self):
        '''JSON representation'''
        return {
            'id': self.id,
            'node_id': self.node_id,
            'name': None,
            'user_id': self.user_id,
            'allowed': self.allowed,
            'pv': None,
            'network_pv': None,
            'when_updated': None,
            'when_created': self.when_created,
            'when_changed': self.when_changed
        }
