from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel
from app.orders.models import Order
from app.modules.warehouse.models import Warehouse

class WarehouseOrder(db.Model, BaseModel):
    '''Represents an clientless order for the warehouse'''
    __tablename__ = 'warehouse_orders'

    id = None
    order_id = Column(String(16), ForeignKey('orders.id'), primary_key=True)
    order = relationship('Order', foreign_keys=[order_id])
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'))
    warehouse = relationship(Warehouse, foreign_keys=[warehouse_id])

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'warehouse_id': self.warehouse_id,
            'warehouse': self.warehouse.name if self.warehouse is not None else None
        }
