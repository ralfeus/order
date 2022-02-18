from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from app import db
from app.models.base import BaseModel
from app.products.models.product import Product

class Warehouse(db.Model, BaseModel):
    '''Represents a warehouse'''
    __tablename__ = 'warehouses'

    name = Column(String(128))
    is_local = Column(Boolean, default=False)
    products = association_proxy('warehouse_products', 'quantity',
        creator=lambda k, v: WarehouseProduct(product=k, quantity=v)
    )

    @classmethod
    def get_local(cls):
        return cls.query.filter_by(is_local=True).first()

    def __repr__(self) -> str:
        return f"{self.id}: {self.name}"

    def __str__(self) -> str:
        return f"{self.id}: {self.name}"

    def add_product(self, product, quantity):
        if self.products.get(product) is None:
            self.products[product] = 0
        self.products[product] += quantity

    def sub_product(self, product, quantity):
        self.add_product(product, -quantity)

    def is_product_available(self, product):
        return self.products.get(product, 0) > 0

    def to_dict(self, details=False):
        return {
            'id': self.id,
            'name': self.name,
            'is_local': self.is_local,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }

class WarehouseProduct(db.Model):
    '''Intermediate entity represents a product in the warehouse'''
    __tablename__ = 'warehouse_products'

    warehouse_id = Column(Integer, ForeignKey('warehouses.id'), primary_key=True)
    warehouse = relationship(Warehouse,
        backref=backref('warehouse_products',
            collection_class=attribute_mapped_collection('product'),
            cascade='all, delete-orphan')
    )
    product_id = Column(String(16), ForeignKey('products.id'), primary_key=True)
    product = relationship(Product)
    quantity = Column(Integer)

    def to_dict(self):
        return {
            'warehouse_id': self.warehouse_id,
            'warehouse': self.warehouse.to_dict(),
            'product_id': self.product_id,
            'product': {
                'name': self.product.name,
                'name_english': self.product.name_english,
                'name_russian': self.product.name_russian,
            },
            'quantity': self.quantity
        }
