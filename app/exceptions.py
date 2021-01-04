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

class SubcustomerParseError(Exception):
    pass
