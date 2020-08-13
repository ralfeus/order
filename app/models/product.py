'''
Product model
'''
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app import db

class Product(db.Model):
    '''
    Represents a product
    '''
    __tablename__ = 'products'

    id = Column(String(16), primary_key=True)
    name = Column(String(256), index=True)
    name_english = Column(String(256), index=True)
    name_russian = Column(String(256), index=True)
    category = Column(String(64))
    weight = Column(Integer)
    price = Column(Integer)
    points = Column(Integer)
    available = Column(Boolean, default=True)
    when_created = Column(DateTime)
    when_changed = Column(DateTime)

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
            'price': self.price,
            'weight': self.weight,
            'points': self.points,
            'available': self.available
        }
