''' Node model'''
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean

from app import db
from app.models.base import BaseModel

class Node(BaseModel, db.Model):
    '''Node model'''
    __tablename__ = 'network_nodes'
    id = Column(String(10), primary_key=True)
    name = Column(String(64))
    rank = Column(String(16), index=True)
    highest_rank = Column(String(16))
    center = Column(String(64))
    country = Column(String(32))
    signup_date = Column(Date())
    pv = Column(Integer())
    network_pv = Column(Integer())

    parent_id = Column(String(10), ForeignKey('network_nodes.id'))
    parent = relationship("Node", foreign_keys=[parent_id], uselist=False)
    left_id = Column(String(10))#, ForeignKey('network_nodes.id'))
    # left = relationship("Node", foreign_keys=[parent_id], uselist=False)
    right_id = Column(String(10))#, ForeignKey('network_nodes.id'))
    # right = relationship("Node", foreign_keys=[parent_id], uselist=False)
    built_tree = Column(Boolean(), index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'left_id': self.left_id,
            'right_id': self.right_id,
            'name': self.name,
            'rank': self.rank,
            'highest_rank': self.highest_rank,
            'center': self.center,
            'country': self.country,
            'pv': self.pv,
            'network_pv': self.network_pv,
            'signup_date': self.signup_date.strftime('%Y-%m-%d') \
                if self.signup_date else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
