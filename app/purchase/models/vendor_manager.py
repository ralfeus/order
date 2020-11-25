''' Provides purchase order vendors '''
class PurchaseOrderVendorManager:
    ''' Provides purchase order vendors '''
    @classmethod
    def get_vendors(self, **kwargs):
        from .vendors import vendors
        return [vendor(**kwargs) for vendor in vendors]

    @classmethod
    def get_vendor(self, vendor_id, **kwargs):
        try:
            vendor = [v for v in self.get_vendors(**kwargs) if type(v).__name__ == vendor_id][0]
            return vendor
        except KeyError:
            raise Exception(f"The vendor {vendor_id} doesn't exist")
