'''
Product model
'''
from sqlalchemy import Column, DateTime, Integer, String

from app import db

class Product(db.Model):
    __tablename__ = 'products'

    id = Column(String(16), primary_key=True)
    name = Column(String(256), index=True)
    name_english = Column(String(256), index=True)
    name_russian = Column(String(256), index=True)
    category = Column(String(64))
    weight = Column(Integer)
    price = Column(Integer)
    points = Column(Integer)
    when_created = Column(DateTime)
    when_changed = Column(DateTime)

    def __repr__(self):
        return "<Product {}:'{}'>".format(self.id, self.name_english)

    @staticmethod
    def get_products(product_query):
        '''
        Returns list of products based on a query
        '''
        return list(map(lambda product: {
            'id': product.id,
            'name': product.name,
            'name_english': product.name_english,
            'name_russian': product.name_russian,
            'price': product.price,
            'weight': product.weight,
            'points': product.points
            }, product_query))
