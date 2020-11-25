from abc import ABCMeta, abstractmethod
from datetime import datetime
from app.orders.models import Subcustomer
from app.purchase.models import PurchaseOrder

class PurchaseOrderVendorBase(metaclass=ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return subclass is not cls and cls in subclass.__mro__

    @abstractmethod
    def __init__(self, **kwargs):
        pass

    def __repr__(self):
        return f"Object {self.id}"

    @abstractmethod
    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        pass

    @abstractmethod
    def update_purchase_orders_status(self, customer: Subcustomer, customer_pos: list):
        pass

    def _set_order_products_status(self, ordered_products, status):
        for op in ordered_products:
            op.status = status
            op.when_changed = datetime.now()

    def to_dict(self):
        return {self.id: str(self)}

    @property
    def id(self):
        return type(self).__name__
