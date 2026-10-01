from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, \
    Numeric, String
from sqlalchemy.orm import relationship

from app import db
from app.invoices.models.invoice import Invoice
from app.products.models import Product
from app.products.models.product import resolve_product_reference
from app.models.base import BaseModel

class InvoiceItem(db.Model, BaseModel):
    '''
    Represents an ordered item of the invoice. Doesn't exist apart from invoice
    '''
    __tablename__ = 'invoice_items'
    __table_args__ = (
        ForeignKeyConstraint(['product_id', 'product_vendor'],
                             ['products.id', 'products.vendor']),
    )

    invoice_id = Column(String(16), ForeignKey('invoices.id'))
    invoice = relationship('Invoice', foreign_keys=[invoice_id], back_populates='_invoice_items')
    # Not always a product. E.g. "SHIPPING" has no vendor and refers to no product
    product_id = Column(String(16))
    product_vendor = Column(String(16))
    product = relationship('Product')
    price = Column(Numeric(scale=2))
    quantity = Column(Integer)

    def __init__(self, **kwargs):
        resolve_product_reference(kwargs)
        super().__init__(**kwargs)

    @property
    def product_key(self) -> str:
        '''Product key. Items without product (e.g. "SHIPPING") are identified by product ID.
        Product is used as unsaved items (made from order products) have no vendor set yet'''
        return self.product.key if self.product else self.product_id

    def __repr__(self):
        return f"<InvoiceItem: {self.id} - Invoice: {self.invoice_id}>"

    def to_dict(self):
        if self.product is None:
            name = "--Non-existing product--"
            weight = 0
        else:
            name = self.product.name_english \
                if self.product.name_english else self.product.name
            weight = self.product.weight
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'product_id': self.product_id,
            'product_vendor': self.product.vendor if self.product else self.product_vendor,
            'product_key': self.product_key,
            'product': name,
            'weight': weight,
            'price': float(self.price),
            'quantity': self.quantity,
            'subtotal': round(float(self.price * self.quantity), 2),
            'when_created': self.when_created,
            'when_changed': self.when_changed
        }
