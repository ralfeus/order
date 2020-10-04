'''
Product model
'''
from sqlalchemy import Boolean, Column, Integer, String

from app import db
from app.models.base import BaseModel

class Product(db.Model, BaseModel):
    '''
    Represents a product
    '''
    __tablename__ = 'products'

    id = Column(String(16), primary_key=True)
    name = Column(String(256), index=True)
    name_english = Column(String(256), index=True)
    name_russian = Column(String(256), index=True)
    category = Column(String(64))
    weight = Column(Integer, default=0)
    price = Column(Integer)
    points = Column(Integer)
    separate_shipping = Column(Boolean, default=False)
    available = Column(Boolean, default=True)
    synchronize = Column(Boolean, default=True)

    def __repr__(self):
        return "<Product {}:'{}'>".format(self.id, self.name_english)

    @staticmethod
    def get_products(product_query):
        '''
        Returns list of products based on a query
        '''
        return list(map(lambda product: product.to_dict(), product_query))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_english': self.name_english,
            'name_russian': self.name_russian,
            'price': self.price if self.price else 0,
            'weight': self.weight if self.weight else 0,
            'points': self.points if self.points else 0,
            'separate_shipping': self.separate_shipping if self.separate_shipping else 0,
            'available': self.available,
            'synchronize': self.synchronize
        }
