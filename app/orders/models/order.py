'''
Order model
'''
import enum
from datetime import datetime
from decimal import Decimal
from functools import reduce

from sqlalchemy import Column, Enum, DateTime, Numeric, ForeignKey, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.shipping.models import Shipping, NoShipping
from app.invoices.models import Invoice
from app.currencies.models import Currency

class OrderStatus(enum.Enum):
    pending = 1
    paid = 2
    po_created = 3
    shipped = 4
    complete = 5

class Order(db.Model):
    ''' System's order '''
    __tablename__ = 'orders'
    __id_pattern = 'ORD-{year}-{month:02d}-'

    id = Column(String(16), primary_key=True, nullable=False)
    seq_num = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    invoice_id = Column(String(16), ForeignKey('invoices.id'))
    invoice = relationship('Invoice', foreign_keys=[invoice_id])
    name = Column(String(64))
    address = Column(String(256))
    country_id = Column(String(2), ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id])
    phone = Column(String(64))
    comment = Column(String(128))
    shipping_box_weight = Column(Integer())
    total_weight = Column(Integer(), default=0)
    shipping_method_id = Column(Integer, ForeignKey('shipping.id'))
    __shipping = relationship("Shipping", foreign_keys=[shipping_method_id])
    subtotal_krw = Column(Integer(), default=0)
    subtotal_rur = Column(Numeric(10, 2), default=0)
    subtotal_usd = Column(Numeric(10, 2), default=0)
    shipping_krw = Column(Integer(), default=0)
    shipping_rur = Column(Numeric(10, 2), default=0)
    shipping_usd = Column(Numeric(10, 2), default=0)
    total_krw = Column(Integer(), default=0)
    total_rur = Column(Numeric(10, 2), default=0)
    total_usd = Column(Numeric(10, 2), default=0)
    __status = Column('status', Enum(OrderStatus))
    tracking_id = Column(String(64))
    tracking_url = Column(String(256))
    when_created = Column(DateTime)
    when_changed = Column(DateTime)
    suborders = relationship('Suborder', lazy='dynamic')
    __order_products = relationship('OrderProduct', lazy='dynamic')

    @hybrid_property
    def status(self):
        return self.__status

    @status.setter
    def status(self, value) -> Column:
        if isinstance(value, str):
            value = OrderStatus[value.lower()]
        elif isinstance(value, int):
            value = OrderStatus(value)

        self.__status = value

    @property
    def shipping(self):
        if self.__shipping is None:
            self.__shipping = NoShipping()
        return self.__shipping

    @shipping.setter
    def shipping(self, value):
        self.__shipping = value

    @property
    def order_products(self):
        if self.suborders.count() > 0:
            return [order_product for suborder in self.suborders
                                  for order_product in suborder.order_products]
        else:
            return list(self.__order_products)

    def __init__(self, **kwargs):
        today = datetime.now()
        today_prefix = self.__id_pattern.format(year=today.year, month=today.month)
        last_order = db.session.query(Order.seq_num). \
            filter(Order.id.like(today_prefix + '%')). \
            order_by(Order.when_created.desc()). \
            first()
        self.seq_num = last_order[0] + 1 if last_order else 1
        self.id = today_prefix + '{:04d}'.format(self.seq_num)

        self.total_weight = 0
        self.total_krw = 0

        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])
        # Here properties are set (attributes start with '__')
        if kwargs.get('shipping'):
            self.shipping = kwargs['shipping']
        if kwargs.get('status'):
            self.status = kwargs['status']

    def __repr__(self):
        return "<Order: {}>".format(self.id)

    def to_dict(self):
        if not self.total_krw:
            self.update_total()
        if not self.total_rur:
            self.total_rur = self.total_krw * Currency.query.get('RUR').rate
        if not self.total_usd:
            self.total_usd = self.total_krw * Currency.query.get('USD').rate
        return {
            'id': self.id,
            'user': self.user.username if self.user else None,
            'customer': self.name,
            'address': self.address,
            'phone': self.phone,
            'invoice_id': self.invoice_id,
            'subtotal_krw': self.subtotal_krw,
            'shipping_krw': self.shipping_krw,
            'total': self.total_krw,
            'total_krw': self.total_krw,
            'total_rur': float(self.total_rur),
            'total_usd': float(self.total_usd),
            'country': self.country.to_dict() if self.country else None,
            'shipping': self.shipping.to_dict() if self.shipping else None,
            'status': self.status.name if self.status else None,
            'tracking_id': self.tracking_id if self.tracking_id else None,
            'tracking_url': self.tracking_url if self.tracking_url else None,
            'suborders': [suborder.to_dict() for suborder in self.suborders],
            'order_products': [order_product.to_dict() for order_product in self.order_products],
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else None
        }

    def update_total(self):
        '''
        Updates totals of the order
        '''
        for suborder in self.suborders:
            suborder.update_total()

        if self.shipping is None and self.shipping_method_id is not None:
            self.shipping = Shipping.query.get(self.shipping_method_id)

        self.total_weight = reduce(lambda acc, sub: acc + sub.total_weight,
                                   self.suborders, 0)
        self.shipping_box_weight = self.shipping.get_box_weight(self.total_weight)

        # self.subtotal_krw = reduce(lambda acc, op: acc + op.price * op.quantity,
        #                            self.order_products, 0)
        self.subtotal_krw = reduce(
            lambda acc, sub: acc + sub.total_krw, self.suborders, 0)
        self.subtotal_rur = self.subtotal_krw * Currency.query.get('RUR').rate
        self.subtotal_usd = self.subtotal_krw * Currency.query.get('USD').rate

        self.shipping_krw = int(Decimal(self.shipping.get_shipping_cost(
            self.country.id if self.country else None, 
            self.total_weight + self.shipping_box_weight)))
        self.shipping_rur = self.shipping_krw * Currency.query.get('RUR').rate
        self.shipping_usd = self.shipping_krw * Currency.query.get('USD').rate

        self.total_krw = self.subtotal_krw + self.shipping_krw
        self.total_rur = self.subtotal_rur + self.shipping_rur
        self.total_usd = self.subtotal_usd + self.shipping_usd
