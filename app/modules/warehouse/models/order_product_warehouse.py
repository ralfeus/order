from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.orders.models.order_product import OrderProduct
from app.modules.warehouse.models.warehouse import Warehouse

class OrderProductWarehouse(db.Model, BaseModel):
    '''Represents a warehouse usage for an order product'''
    __tablename__ = 'order_products_warehouses'

    order_product_id = Column(Integer)
    order_product = relationship(OrderProduct, foreign_keys=[order_product_id])
    warehouse_id = Column(Integer)
    warehouse = relationship(Warehouse, foreign_keys=[warehouse_id])

    def to_dict(self):
        return {
            'order_product_id': self.order_product_id,
            'warehouse_id': self.warehouse_id,
            'warehouse': self.warehouse.name if self.warehouse is not None else None
        }
