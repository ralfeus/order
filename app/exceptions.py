class AtomyLoginError(Exception):
    pass

class EmptySuborderError(Exception):
    pass

class NoPurchaseOrderError(Exception):
    pass

class NoShippingRateError(Exception):
    pass

class OrderError(Exception):
    pass

class PaymentNoReceivedAmountException(Exception):
    pass

class ProductNotAvailableError(Exception):
    def __init__(self, product_id, final=False):
        super().__init__()
        self.product_id = product_id
        self.final = final

    def __str__(self):
        return f"Product {self.product_id} is not available"

class ProductNotFoundError(Exception):
    def __init__(self, product_id):
        super().__init__()
        self.product_id = product_id

    def __str__(self):
        return f"Product {self.product_id} was not found"

class PurchaseOrderError(Exception):
    def __init__(self, po, vendor, message, retry=False):
        self.message = message
        self.po_id = po.id
        self.retry = retry
        self.vendor = str(vendor)
    
    def __str__(self):
        return f"Couldn't post PO {self.po_id} at {self.vendor}: {self.message}"

class SubcustomerParseError(Exception):
    pass

class UnfinishedOrderError(Exception):
    def __init__(self, items):
        super().__init__()
        self.__items = items
   
    def __str__(self):
        return "The order is not finished: \n" + "\n".join(self.__items)
