class AtomyLoginError(Exception):
    def __init__(self, username=None, password=None, message=None):
        super().__init__()
        self.username = username
        self.password = password
        self.message = message
        self.args = (username, message)

    def __str__(self):
        return f"Couldn't log in as '{self.username}':'{self.password}': {self.message}"

class NoPurchaseOrderError(Exception):
    pass
    
class PurchaseOrderError(Exception):
    def __init__(self, po=None, message=None, retry=False, screenshot=False):
        super().__init__()
        self.final = False
        self.message = message
        self.po_id = po.id if po else None
        self.retry = retry
        self.screenshot = screenshot
        self.args = (message,)
    
    def __str__(self):
        return f"Couldn't post {self.po_id}: {self.message}"

class ProductNotAvailableError(PurchaseOrderError):
    def __init__(self, product_id, message='', final=False):
        super().__init__()
        self.product_id = product_id
        self.message = message
        self.final = final

    def __str__(self):
        return f"Product {self.product_id} is not available: {self.message}"

