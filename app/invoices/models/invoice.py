'''
Invoice model
'''
from datetime import datetime
import logging

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.shipping.models.shipping import Shipping

class Invoice(db.Model):  # type: ignore
    '''
    Invoice model
    '''
    __tablename__ = 'invoices'
    __id_pattern = 'INV-{year}-{month:02d}-'

    id = Column(String(16), primary_key=True)
    seq_num = Column(Integer)
    customer = Column(String(128))
    payee = Column(String(32))
    orders = relationship('Order')
    export_id = Column(String(32))
    currency_code = Column(String(3), ForeignKey('currencies.code'), nullable=False)
    _invoice_items = relationship('InvoiceItem', lazy='dynamic')
    #total = Column(Integer)

    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)

    def get_invoice_items(self):
        logger = logging.getLogger('get_invoice_items')
        if self._invoice_items.count() > 0:
            return self._invoice_items
        else:
            logger.info("Getting items for %s from order products", self.id)
            from app.currencies.models import Currency
            from app.invoices.models import InvoiceItem
            temp_invoice_items = []
            currency = Currency.query.get(self.currency_code)
            rate = currency.get_rate(self.when_created) \
                if currency else 1.0
            for order in self.orders:
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
                        price=round(order_product.price * rate, 2),
                        quantity=order_product.quantity
                    ))
            return temp_invoice_items
    
    @property
    def invoice_items_count(self):
        '''
        Dirty hack of getting count of elements for backward compatibility
        '''
        ii = self.get_invoice_items()
        if isinstance(ii, list):
            return len(ii)
        else:
            return ii.count()


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

    def __repr__(self):
        return f"<Invoice: {self.id}>"

    @classmethod
    def get_filter(cls, base_filter, column = None, filter_value = None):
        if column is None or filter_value is None:
            return base_filter
        from app.orders.models.order import Order
        part_filter = f'%{filter_value}%'
        if isinstance(column, str):
            return \
                base_filter.filter(cls.orders.any(Order.shipping.has(Shipping.name.like(part_filter)))) \
                    if column == 'shippings' \
                else base_filter
        return \
            base_filter.filter(column.any(Order.id.like(part_filter))) \
                if column.key == 'orders' \
            else base_filter.filter(column.like(f'%{filter_value}%'))

    def to_dict(self, details=False):
        '''
        Returns dictionary of the invoice ready to be jsonified
        '''
        invoice_items_dict = {}
        total = 0
        weight = 0
        for invoice_item in self.get_invoice_items():
            total += invoice_item.price * invoice_item.quantity
            weight += invoice_item.product.weight * invoice_item.quantity \
                if invoice_item.product is not None else 0
            if invoice_items_dict.get(invoice_item.product_id):
                invoice_items_dict[invoice_item.product_id]['quantity'] += invoice_item.quantity
                invoice_items_dict[invoice_item.product_id]['subtotal'] = \
                    round(invoice_items_dict[invoice_item.product_id]['subtotal'] +
                          float(invoice_item.price * invoice_item.quantity), 2)
            else:
                invoice_items_dict[invoice_item.product_id] = invoice_item.to_dict()
        # print(f"{self.id}: orders {','.join(map(lambda o: str(o.id), self.orders))}")
        is_dirty = False
        if not self.customer and self.orders:
            self.customer = self.orders[0].customer_name
            is_dirty = True
        if not self.payee and self.orders:
            self.payee = self.orders[0].get_payee()
            if self.payee:
                is_dirty = True
        if is_dirty:
            db.session.commit()
        
        result = {
            'id': self.id,
            'customer': self.customer,
            'payee': self.payee,
            'address': self.orders[0].address if self.orders else None,
            'country': self.orders[0].country.name if self.orders else None,
            'phone': self.orders[0].phone if self.orders else None,
            'weight': weight,
            'total': round(float(total), 2),
            'currency_code': self.currency_code,
            'orders': [order.id for order in self.orders],
            'shippings': list({order.shipping.name for order in self.orders 
                               if order.shipping is not None}),
            'export_id': self.export_id,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') 
                            if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') 
                            if self.when_changed else None
        }
        if details:
            result = { **result,
                'invoice_items': list([ii.to_dict() for ii in self.get_invoice_items()])
            }
        return result
