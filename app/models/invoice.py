'''
Invoice model
'''
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

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
    #weight = Column(Integer)
    #total = Column(Integer)

    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)

    def __init__(self):
        today = datetime.now()
        today_prefix = self.__id_pattern.format(year=today.year, month=today.month)
        last_invoice = db.session.query(Invoice.seq_num). \
            filter(Invoice.id.like(today_prefix + '%')). \
            order_by(Invoice.when_created.desc()). \
            first()
        self.seq_num = last_invoice[0] + 1 if last_invoice else 1
        self.id = today_prefix + '{:04d}'.format(self.seq_num)

    def to_dict(self):
        '''
        Returns dictionary of the invoice ready to be jsonified
        '''
        order_products_dict = {}
        total = 0
        weight = 0
        for order_product in [order_product for order in self.orders
                              for order_product in order.order_products]:
            total += order_product.price * order_product.quantity
            weight += order_product.product.weight * order_product.quantity
            if order_products_dict.get(order_product.product_id):
                order_products_dict[order_product.product_id]['quantity'] += order_product.quantity
                order_products_dict[order_product.product_id]['subtotal'] += \
                    order_product.price * order_product.quantity * \
                        order_products_dict[order_product.product_id]['quantity']
            else:
                order_products_dict[order_product.product_id] = {
                    'product_id': order_product.product_id,
                    'name': order_product.product.name,
                    'price': order_product.price,
                    'quantity': order_product.quantity,
                    'subtotal': order_product.price * order_product.quantity
                }
        print(f"{self.id}: orders {','.join(map(lambda o: o.id, self.orders))}")

        return {
            'id': self.id,
            'customer': self.orders[0].name if self.orders else '',
            'address': self.orders[0].address if self.orders else '',
            'country': self.orders[0].country if self.orders else '',
            'phone': self.orders[0].phone if self.orders else '',
            'weight': weight,
            'total': total,
            'when_created': self.when_created,
            'when_changed': self.when_changed,
            'orders': [order.id for order in self.orders],
            'order_products': list(order_products_dict.values())
        }
