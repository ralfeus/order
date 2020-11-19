from app.purchase.models import PurchaseOrder
from . import PurchaseOrderVendorBase

class AtomyCenter(PurchaseOrderVendorBase):
    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        pass

    def __str__(self):
        return "Atomy - Center"