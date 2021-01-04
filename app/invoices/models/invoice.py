'''
Invoice model
'''
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.models.base import BaseModel
from app.orders.models.order import Order

class Invoice(BaseModel, db.Model):
    '''
    Invoice model
    '''
    __tablename__ = 'invoices'
    __id_pattern = 'INV-{year}-{month:02d}-'

    id = Column(String(16), primary_key=True)
    seq_num = Column(Integer)
    customer = Column(String(128))
    address = Column(String(256))
    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship("Country", foreign_keys=[country_id])
    phone = Column(String(64))
    _invoice_items = relationship('InvoiceItem', lazy='dynamic')
    #total = Column(Integer)

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

    def add_invoice_component(self, invoice):
        if self.customer is None:
            self.customer = invoice.customer
        if self.address is None:
            self.address = invoice.address
        if self.country_id is None:
            self.country_id = invoice.country_id
        if self.country is None:
            self.country = invoice.country
        if self.phone is None:
            self.phone = invoice.phone
        self._invoice_items.append = invoice.get_invoice_items()

    def get_orders(self):
        return Order.query.filter_by(invoice_id=self.id).all()

    def get_invoice_items(self):
        if self._invoice_items.count() > 0:
            return self._invoice_items.all()

        from app.currencies.models import Currency
        from app.invoices.models import InvoiceItem
        temp_invoice_items = []
        usd_rate = Currency.query.get('USD').rate
        orders = self.get_orders()
        if orders is None:
            orders = [self.get_order()]
        
        for order in orders:
            order_products = None
            if order.suborders.count() > 0:
                order_products = [order_product for suborder in order.suborders
                                                for order_product in suborder.order_products]
            else:
                order_products = order.order_products
            for order_product in order_products:
                temp_invoice_items.append(InvoiceItem(
                    id=len(temp_invoice_items) + 1,
                    invoice_id=self.id,
                    invoice=self,
                    product_id=order_product.product.id,
                    product=order_product.product,
                    price=round(order_product.price * usd_rate, 2),
                    quantity=order_product.quantity
                ))
        return temp_invoice_items
    
    @property
    def invoice_items_count(self):
        '''
        Dirty hack of getting count of elements for backward compatibility
        '''
        return len(self.get_invoice_items())

    def __repr__(self):
        return f"<Invoice: {self.id}>"

    def to_dict(self):
        '''
        Returns dictionary of the invoice ready to be jsonified
        '''
        invoice_items_dict = {}
        total = 0
        weight = 0
        for invoice_item in self.get_invoice_items():
            total += invoice_item.price * invoice_item.quantity
            weight += invoice_item.product.weight * invoice_item.quantity
            if invoice_items_dict.get(invoice_item.product_id):
                invoice_items_dict[invoice_item.product_id]['quantity'] += invoice_item.quantity
                invoice_items_dict[invoice_item.product_id]['subtotal'] = \
                    round(invoice_items_dict[invoice_item.product_id]['subtotal'] +
                          float(invoice_item.price * invoice_item.quantity), 2)
            else:
                invoice_items_dict[invoice_item.product_id] = invoice_item.to_dict()
        # print(f"{self.id}: orders {','.join(map(lambda o: str(o.id), self.orders))}")
        return {
            'id': self.id,
            'customer': self.customer,
            'address': self.address,
            'country': self.country.name if self.country else None,
            'phone': self.phone,
            'weight': weight,
            'total': round(float(total), 2),
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') 
                            if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') 
                            if self.when_changed else None,
            'orders': [order.id for order in self.get_orders()],
            'invoice_items': list([ii.to_dict() for ii in self.get_invoice_items()])
        }
