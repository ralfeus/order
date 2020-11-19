from abc import ABCMeta, abstractmethod
from app.purchase.models import PurchaseOrder

class PurchaseOrderVendorBase(metaclass=ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return subclass is not cls and cls in subclass.__mro__

    @abstractmethod
    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        pass

    def __repr__(self):
        return f"<{type(self)}>"

    def to_dict(self):
        return {str(type(self)): str(self)}