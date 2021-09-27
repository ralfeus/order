''' Provides purchase order vendors '''
class PurchaseOrderVendorManager:
    ''' Provides purchase order vendors '''
    @classmethod
    def get_vendors(self, **kwargs):
        from .vendors import vendors
        return [vendor(**kwargs) for vendor in vendors]

    @classmethod
    def get_vendor(self, vendor_id, **kwargs):
        from .vendors import vendors
        try:
            vendor = [v for v in vendors if v.__name__ == vendor_id][0](**kwargs)
            return vendor
        except KeyError:
            raise Exception(f"The vendor {vendor_id} doesn't exist")
