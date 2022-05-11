''' Provides purchase order vendors '''
from flask import current_app
from app.purchase.models.vendors.vendor_base import PurchaseOrderVendorBase

class PurchaseOrderVendorManager:
    ''' Provides purchase order vendors '''
    @classmethod
    def get_vendors(self, **kwargs):
        from .vendors import vendors
        return [vendor(**kwargs) for vendor in vendors
            if 'AtomyCenter' not in str(vendor) or current_app.config.get('ATOMY_CENTER')]

    @classmethod
    def get_vendor(self, vendor_id, **kwargs) -> PurchaseOrderVendorBase:
        from .vendors import vendors
        try:
            vendor = [v for v in vendors 
                if v.__name__ == vendor_id and
                ('AtomyCenter' not in str(v) or current_app.config.get('ATOMY_CENTER'))][0](**kwargs)
            return vendor
        except KeyError:
            raise Exception(f"The vendor {vendor_id} doesn't exist")
