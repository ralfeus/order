from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app import db
from app.invoices.models.invoice import Invoice
from app.models.base import BaseModel

class InvoiceItem(db.Model, BaseModel):
    '''
    Represents an ordered item of the invoice. Doesn't exist apart from invoice
    '''
    __tablename__ = 'invoice_items'

    invoice_id = Column(String(16), ForeignKey('invoices.id'))
    invoice = relationship('Invoice', foreign_keys=[invoice_id])
    product_id = Column(String(16), ForeignKey('products.id'))
    product = relationship('Product')
    price = Column(Numeric(scale=2))
    quantity = Column(Integer)

    def __repr__(self):
        return f"<InvoiceItem: {self.id} - Invoice: {self.invoice_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'product_id': self.product_id,
            'product': self.product.name_english \
                if self.product.name_english else self.product.name,
            'weight': self.product.weight,
            'price': float(self.price),
            'quantity': self.quantity,
            'subtotal': float(self.price * self.quantity),
            'when_created': self.when_created,
            'when_changed': self.when_changed
        }
