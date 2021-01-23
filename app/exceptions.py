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
    def __init__(self, product_id):
        super().__init__()
        self.product_id = product_id

    def __str__(self):
        return f"Product {self.product_id} is not available"

class ProductNotFoundError(Exception):
    def __init__(self, product_id):
        super().__init__()
        self.product_id = product_id

    def __str__(self):
        return f"Product {self.product_id} was not found"

class SubcustomerParseError(Exception):
    pass
