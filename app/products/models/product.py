'''
Product model
'''
from __future__ import annotations
from sqlalchemy import Boolean, Column, ForeignKey, ForeignKeyConstraint, Integer, \
    String, UniqueConstraint
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.models.file import File
from app.shipping.models.shipping import Shipping

DEFAULT_VENDOR = 'Atomy'
VENDORS = (DEFAULT_VENDOR, 'AtomyAza')
KEY_SEPARATOR = ':'

class AmbiguousProductError(Exception):
    '''Raised when a product ID matches products of several vendors'''

_products_shipping = db.Table('products_shipping',
    Column('product_id', String(16)),
    Column('product_vendor', String(16)),
    Column('shipping_method_id', Integer, ForeignKey('shipping.id')),
    ForeignKeyConstraint(['product_id', 'product_vendor'], ['products.id', 'products.vendor']),
    UniqueConstraint('product_id', 'product_vendor', 'shipping_method_id')
)

class Product(db.Model, BaseModel): #type: ignore
    '''
    Represents a product
    '''
    __tablename__ = 'products'

    id = Column(String(16), primary_key=True)
    # Catalog the product comes from (not a purchase order vendor)
    vendor = Column(String(16), primary_key=True, default=DEFAULT_VENDOR,
                    server_default=DEFAULT_VENDOR, index=True)
    vendor_id = Column(String(16), index=True)
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
    available_shipping = relationship(Shipping, secondary=_products_shipping, lazy='select')
    # Appearance
    image_id = Column(Integer, ForeignKey('files.id'))
    image = relationship(File, uselist=False)
    color = Column(String(7))

    def __repr__(self):
        return "<Product {}:'{}'>".format(self.id, self.name_english)

    def get_available_shipping(self):
        if len(self.available_shipping) > 0:
            return self.available_shipping
        else:
            return Shipping.query

    @classmethod
    def get_filter(cls, base_filter, column = None, filter_value = None):
        if column is None or filter_value is None:
            return base_filter
        part_filter = f'%{filter_value}%'
        return \
            base_filter.filter(cls.available.in_(filter_value.split(','))) \
                if column.key == 'available' else \
            base_filter.filter(cls.purchase.in_(filter_value.split(','))) \
                if column.key == 'purchase' \
            else base_filter.filter(column.like(part_filter))

    @property
    def key(self) -> str:
        '''Product identifier unique across vendors: "<vendor>:<id>"'''
        return f'{self.vendor}{KEY_SEPARATOR}{self.id}'

    @staticmethod
    def split_key(identifier: str) -> tuple[str | None, str]:
        '''Splits "<vendor>:<id>" into vendor and ID. Product ID may contain
        the separator, vendor may not. If the identifier doesn't start with
        a known vendor, it's a product ID of any vendor: (None, identifier)'''
        vendor, _, product_id = identifier.partition(KEY_SEPARATOR)
        if vendor in VENDORS and product_id:
            return vendor, product_id
        return None, identifier

    @classmethod
    def get_by_key(cls, key: str) -> Product | None:
        '''Returns product by exact "<vendor>:<id>" key'''
        vendor, product_id = cls.split_key(key or '')
        if vendor is None:
            return None
        return cls.query.filter_by(vendor=vendor, id=product_id).first()

    @classmethod
    def _single(cls, products: list[Product], identifier: str) -> Product | None:
        if len(products) > 1:
            raise AmbiguousProductError(
                f"More than one product was found by code <{identifier}>: " +
                ', '.join(sorted(p.key for p in products)))
        return products[0] if products else None

    @classmethod
    def resolve(cls, identifier: str | None) -> Product | None:
        '''Returns product by exact "<vendor>:<id>" key or product ID.
        Raises AmbiguousProductError if the product ID exists in several vendors'''
        if not identifier:
            return None
        vendor, product_id = cls.split_key(identifier)
        query = cls.query.filter_by(id=product_id)
        if vendor is not None:
            query = query.filter_by(vendor=vendor)
        return cls._single(query.all(), identifier)

    @classmethod
    def find_by_code(cls, code: str) -> Product | None:
        '''Finds product by code typed by a user. The code is either
        a product ID looked up across all vendors or "<vendor>:<id>".
        Leading zeros of the ID are ignored.
        Raises AmbiguousProductError if the code matches several products'''
        vendor, product_id = cls.split_key(code)
        query = cls.query
        if vendor is not None:
            query = query.filter_by(vendor=vendor)
        stripped_id = product_id.lstrip('0')
        products = [product for product in query.filter(cls.id.endswith(stripped_id))
                    if product.id.lstrip('0') == stripped_id]
        return cls._single(products, code)

    @staticmethod
    def get_product_by_id(product_id):
        return Product.find_by_code(product_id)

    def to_dict(self, details=False):
        result = {
            'id': self.id,
            'vendor': self.vendor,
            'key': self.key,
            'vendor_id': self.vendor_id,
            'name': self.name,
            'name_english': self.name_english,
            'name_russian': self.name_russian,
            'price': self.price if self.price else 0,
            'weight': self.weight if self.weight else 0,
            'points': self.points if self.points else 0,
            'separate_shipping': self.separate_shipping if self.separate_shipping else False,
            'available': self.available,
            'synchronize': self.synchronize,
            'purchase': self.purchase,
            'color': self.color,
            'image': self.image.path if self.image is not None else "/static/images/no_image.jpg"
        }
        if details:
            result = {**result,
                'shipping': [shipping.to_dict() for shipping in self.get_available_shipping()]
            }
        return result


def resolve_product_reference(kwargs: dict) -> None:
    '''Sets "product" of an entity referring to a product being created
    with "product_id", which is either a product key or a product ID.
    Raises AmbiguousProductError if the product ID exists in several vendors'''
    if kwargs.get('product') is None and kwargs.get('product_id'):
        product = Product.resolve(kwargs['product_id'])
        if product is not None:
            del kwargs['product_id']
            kwargs['product'] = product
