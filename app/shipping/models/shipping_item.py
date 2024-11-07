class ShippingItem:
    def __init__(self, name: str, quantity: int, price: float, **kwargs):
        self.name = name
        self.quantity = quantity
        self.price = price
        self.attributes = kwargs