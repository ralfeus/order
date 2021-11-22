from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from app import db
from app.models.base import BaseModel
from app.orders.models.order_product import OrderProduct
from app.modules.warehouse.models.warehouse import Warehouse

class OrderProductWarehouse(db.Model, BaseModel):
    '''Represents a warehouse usage for an order product'''
    __tablename__ = 'order_products_warehouses'

    id = None
    order_product_id = Column(Integer, ForeignKey('order_products.id'), primary_key=True)
    order_product = relationship(OrderProduct, foreign_keys=[order_product_id])
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'))
    warehouse = relationship(Warehouse, foreign_keys=[warehouse_id])

    def to_dict(self):
        return {
            'order_product_id': self.order_product_id,
            'warehouse_id': self.warehouse_id,
            'warehouse': self.warehouse.name if self.warehouse is not None else None
        }

    @classmethod
    def get_warehouse_for_order_product(cls, order_product):
        op_warehouse = cls.query.filter_by(order_product_id=order_product.id).first()
        return \
            op_warehouse.to_dict() if op_warehouse is not None \
            else {
                'warehouse': None,
                'warehouse_id': None
            }
