'''
Product model
'''
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.models.file import File
from app.shipping.models import Shipping

_products_shipping = db.Table('products_shipping',
    Column('product_id', String(16), ForeignKey('products.id')),
    Column('shipping_method_id', Integer, ForeignKey('shipping.id'))
)

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
    points = Column(Integer, default=0)
    separate_shipping = Column(Boolean, default=False)
    available = Column(Boolean, default=True)
    synchronize = Column(Boolean, default=True)
    purchase = Column(Boolean, default=True)
    available_shipping = relationship(Shipping, secondary=_products_shipping, lazy='dynamic')
    # Appearance
    image_id = Column(Integer, ForeignKey('files.id'))
    image = relationship(File, uselist=False)
    color = Column(String(7))

    def __repr__(self):
        return "<Product {}:'{}'>".format(self.id, self.name_english)

    def get_available_shipping(self):
        if self.available_shipping.count() > 0:
            return self.available_shipping
        else:
            return Shipping.query

    @classmethod
    def get_filter(cls, base_filter, column, filter_value):
        part_filter = f'%{filter_value}%'
        return \
            base_filter.filter(cls.available.in_(filter_value.split(','))) \
                if column.key == 'available' else \
            base_filter.filter(cls.purchase.in_(filter_value.split(','))) \
                if column.key == 'purchase' \
            else base_filter.filter(column.like(part_filter))

    @staticmethod
    def get_product_by_id(product_id):
        stripped_id = product_id.lstrip('0')
        product_query = Product.query. \
            filter(Product.id.endswith(stripped_id)).all()
        products = [product for product in product_query
                        if product.id.lstrip('0') == stripped_id]
        if len(products) == 1:
            return products[0]
        elif len(products) == 0:
            return None
        else:
            raise Exception(f"More than one product was found by ID <{product_id}>")

    def to_dict(self, details=False):
        result = {
            'id': self.id,
            'name': self.name,
            'name_english': self.name_english,
            'name_russian': self.name_russian,
            'price': self.price if self.price else 0,
            'weight': self.weight if self.weight else 0,
            'points': self.points if self.points else 0,
            'separate_shipping': self.separate_shipping if self.separate_shipping else 0,
            'available': self.available,
            'synchronize': self.synchronize,
            'purchase': self.purchase,
            'color': self.color,
        }
        if details:
            result = {**result,
                'shipping': [shipping.to_dict() for shipping in self.get_available_shipping()]
            }
        return result
