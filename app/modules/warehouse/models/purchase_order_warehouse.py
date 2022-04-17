from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from app import db
from app.models.base import BaseModel
from app.modules.warehouse.models.warehouse import Warehouse

class PurchaseOrderWarehouse(db.Model, BaseModel):
    '''Represents a warehouse usage for a purchase order'''
    __tablename__ = 'purchase_order_warehouses'

    id = None
    purchase_order_id = Column(String(23), ForeignKey('purchase_orders.id'), primary_key=True)
    purchase_order = relationship('PurchaseOrder', foreign_keys=[purchase_order_id])
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'))
    warehouse = relationship(Warehouse, foreign_keys=[warehouse_id])

    def to_dict(self):
        return {
            'purchase_order_id': self.purchase_order_id,
            'warehouse_id': self.warehouse_id,
            'warehouse': self.warehouse.name if self.warehouse is not None else None
        }

    @classmethod
    def get_warehouse_for_purchase_order(cls, purchase_order):
        po_warehouse = cls.query.filter_by(purchase_order_id=purchase_order.id).first()
        return \
            po_warehouse.to_dict() if po_warehouse is not None \
            else {
                'warehouse': None,
                'warehouse_id': None
            }
