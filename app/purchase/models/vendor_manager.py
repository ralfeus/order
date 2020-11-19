''' Provides purchase order vendors '''
class PurchaseOrderVendorManager:
    ''' Provides purchase order vendors '''
    def get_vendors(self):
        from .vendors import vendors
        return [vendor() for vendor in vendors]

    def get_vendor(self, vendor_id):
        try:
            vendor = [v for v in self.get_vendors() if str(v) == vendor_id][0]
            return vendor
        except KeyError:
            raise Exception(f"The vendor {vendor_id} doesn't exist")
