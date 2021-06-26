from sqlalchemy import Column, Integer

from app import db
from app.models.base import BaseModel

# class Box(db.Model, BaseModel):
#     ''' Shipping box '''
#     __tablename__ = 'boxes'

#     length = Column(Integer)
#     width = Column(Integer)
#     height = Column(Integer)
#     weight = Column(Integer)

#     def __str__(self) -> str:
#         return f"{self.length}x{self.width}x{self.height} (LxWxH)"

#     def to_dict(self):
#         return {
#             'id': self.id,
#             'description': str(self),
#             'length': self.length,
#             'width': self.width,
#             'height': self.height,
#             'weight': self.weight,
#         }
