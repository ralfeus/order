class AtomyLoginError(Exception):
    def __init__(self, username=None, password=None, message=None):
        super().__init__()
        self.username = username
        self.password = password
        self.message = message
        self.args = (username, message)

    def __str__(self):
        return f"Couldn't log in as '{self.username}':'{self.password}': {self.message}"

class EmptySuborderError(Exception):
    pass

class FilterError(Exception):
    pass

class HTTPError(Exception):
    def __init__(self, status=None):
        super().__init__()
        self.status = status

class NoPurchaseOrderError(Exception):
    pass

class NoShippingRateError(Exception):
    pass

class OrderError(Exception):
    pass

class PaymentNoReceivedAmountException(Exception):
    pass

class PurchaseOrderError(Exception):
    def __init__(self, po=None, vendor=None, message=None, retry=False, screenshot=False):
        super().__init__()
        self.final = False
        self.message = message
        self.po_id = po.id if po else None
        self.retry = retry
        self.screenshot = screenshot
        self.vendor = str(vendor)
        self.args = (message,)
    
    def __str__(self):
        return f"Couldn't post {self.po_id} at {self.vendor}: {self.message}"

class ProductNotAvailableError(PurchaseOrderError):
    def __init__(self, product_id, message='', final=False):
        super().__init__()
        self.product_id = product_id
        self.message = message
        self.final = final

    def __str__(self):
        return f"Product {self.product_id} is not available: {self.message}"

class ProductNotFoundError(Exception):
    def __init__(self, product_id):
        super().__init__()
        self.product_id = product_id

    def __str__(self):
        return f"Product {self.product_id} was not found"

class ShippingException(Exception):
    def __init__(self, message):
        self.message = message

class SubcustomerParseError(Exception):
    pass

class UnfinishedOrderError(Exception):
    def __init__(self, items):
        super().__init__()
        self.__items = items
   
    def __str__(self):
        return "The order is not finished: \n" + "\n".join(self.__items)
