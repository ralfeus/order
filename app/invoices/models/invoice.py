'''
Invoice model
'''
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db

class Invoice(db.Model):
    '''
    Invoice model
    '''
    __tablename__ = 'invoices'
    __id_pattern = 'INV-{year}-{month:02d}-'

    id = Column(String(16), primary_key=True)
    seq_num = Column(Integer)
    orders = relationship('Order')
    _invoice_items = relationship('InvoiceItem', lazy='dynamic')
    #total = Column(Integer)

    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)

    @property
    def invoice_items(self):
        if self._invoice_items.count() > 0:
            return self._invoice_items
        else:
            from app.invoices.models import InvoiceItem
            temp_invoice_items = []
            for order_product in [order_product for order in self.orders
                                                for order_product in order.order_products]:
                temp_invoice_items.append(InvoiceItem(
                    id=len(temp_invoice_items) + 1,
                    invoice_id=self.id,
                    invoice=self,
                    product_id=order_product.product.id,
                    product=order_product.product,
                    price=order_product.price,
                    quantity=order_product.quantity
                ))
            return temp_invoice_items

    def __init__(self, **kwargs):
        today = datetime.now()
        today_prefix = self.__id_pattern.format(year=today.year, month=today.month)
        last_invoice = db.session.query(Invoice.seq_num). \
            filter(Invoice.id.like(today_prefix + '%')). \
            order_by(Invoice.id.desc()). \
            first()
        self.seq_num = last_invoice[0] + 1 if last_invoice else 1
        self.id = today_prefix + '{:04d}'.format(self.seq_num)

        attributes = [a[0] for a in type(self).__dict__.items() if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])


    def to_dict(self):
        '''
        Returns dictionary of the invoice ready to be jsonified
        '''
        invoice_items_dict = {}
        total = 0
        weight = 0
        for invoice_item in self.invoice_items:
            total += invoice_item.price * invoice_item.quantity
            weight += invoice_item.product.weight * invoice_item.quantity
            if invoice_items_dict.get(invoice_item.product_id):
                invoice_items_dict[invoice_item.product_id]['quantity'] += invoice_item.quantity
                invoice_items_dict[invoice_item.product_id]['subtotal'] += \
                    invoice_item.price * invoice_item.quantity * \
                        invoice_items_dict[invoice_item.product_id]['quantity']
            else:
                invoice_items_dict[invoice_item.product_id] = invoice_item.to_dict()
        # print(f"{self.id}: orders {','.join(map(lambda o: str(o.id), self.orders))}")

        return {
            'id': self.id,
            'customer': self.orders[0].name if self.orders else '',
            'address': self.orders[0].address if self.orders else '',
            'country': self.orders[0].country if self.orders else '',
            'phone': self.orders[0].phone if self.orders else '',
            'weight': weight,
            'total': total,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else '',
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else '',
            'orders': [order.id for order in self.orders],
            'invoice_items': list(invoice_items_dict.values())
        }