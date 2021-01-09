'''
Order model
'''
import enum
from datetime import datetime
from decimal import Decimal
from functools import reduce
import os.path
from tempfile import NamedTemporaryFile
import openpyxl
from openpyxl.styles import PatternFill

from sqlalchemy import Column, Enum, DateTime, Numeric, ForeignKey, Integer, String
# from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.exceptions import OrderError
from app.models.base import BaseModel
from app.currencies.models.currency import Currency
from app.payments.models.transaction import Transaction
from app.shipping.models.shipping import Shipping, NoShipping

class OrderStatus(enum.Enum):
    ''' Sale orders statuses '''
    pending = 1
    can_be_paid = 2
    po_created = 3
    # paid = 4
    shipped = 5
    # complete = 6

class Order(db.Model, BaseModel):
    ''' System's order '''
    __tablename__ = 'orders'
    __id_pattern = 'ORD-{year}-{month:02d}-'

    id = Column(String(16), primary_key=True, nullable=False)
    seq_num = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    invoice_id = Column(String(16), ForeignKey('invoices.id'))
    invoice = relationship('Invoice', foreign_keys=[invoice_id])
    customer_name = Column(String(64))
    address = Column(String(256))
    country_id = Column(String(2), ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id])
    zip = Column(String(10))
    phone = Column(String(64))
    comment = Column(String(128))
    shipping_box_weight = Column(Integer())
    total_weight = Column(Integer(), default=0)
    shipping_method_id = Column(Integer, ForeignKey('shipping.id'))
    # __shipping = relationship("Shipping", foreign_keys=[shipping_method_id])
    shipping = relationship("Shipping", foreign_keys=[shipping_method_id])
    subtotal_krw = Column(Integer(), default=0)
    subtotal_rur = Column(Numeric(10, 2), default=0)
    subtotal_usd = Column(Numeric(10, 2), default=0)
    shipping_krw = Column(Integer(), default=0)
    shipping_rur = Column(Numeric(10, 2), default=0)
    shipping_usd = Column(Numeric(10, 2), default=0)
    total_krw = Column(Integer(), default=0)
    total_rur = Column(Numeric(10, 2), default=0)
    total_usd = Column(Numeric(10, 2), default=0)
    status = Column(Enum(OrderStatus),
        default=OrderStatus.pending.name)
    tracking_id = Column(String(64))
    tracking_url = Column(String(256))
    when_created = Column(DateTime)
    when_changed = Column(DateTime)
    purchase_date = Column(DateTime)
    purchase_date_sort = Column(DateTime, index=True,
        nullable=False, default=datetime(9999, 12, 31))
    suborders = relationship('Suborder', lazy='dynamic')
    __order_products = relationship('OrderProduct', lazy='dynamic')
    attached_order_id = Column(String(16), ForeignKey('orders.id'))
    attached_order = relationship('Order', remote_side=[id])
    attached_orders = relationship('Order',
        foreign_keys=[attached_order_id], lazy='dynamic')
    payment_method_id = Column(Integer(), ForeignKey('payment_methods.id'))
    payment_method = relationship('PaymentMethod', foreign_keys=[payment_method_id])
    transaction_id = Column(Integer(), ForeignKey('transactions.id'))
    transaction = relationship('Transaction', foreign_keys=[transaction_id])

    @property
    def order_products(self):
        if self.suborders.count() > 0:
            return [order_product for suborder in self.suborders
                                  for order_product in suborder.order_products]
        return list(self.__order_products)

    def set_purchase_date(self, value):
        self.purchase_date = value
        self.purchase_date_sort = value

    def set_status(self, value, actor):
        if isinstance(value, str):
            value = OrderStatus[value.lower()]
        elif isinstance(value, int):
            value = OrderStatus(value)

        self.status = value
        if value not in [OrderStatus.pending, OrderStatus.can_be_paid]:
            self.purchase_date_sort = datetime(9999, 12, 31)
        if value == OrderStatus.shipped:
            for ao in self.attached_orders:
                ao.set_status(value, actor)
        if value == OrderStatus.shipped:
            self.__pay(actor)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        today = datetime.now()
        today_prefix = self.__id_pattern.format(year=today.year, month=today.month)
        last_order = db.session.query(Order.seq_num). \
            filter(Order.id.like(today_prefix + '%')). \
            order_by(Order.seq_num.desc()). \
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

    def attach_orders(self, orders):
        if orders:
            if isinstance(orders[0], Order):
                self.attached_orders = orders
            else:
                self.attached_orders = Order.query.filter(Order.id.in_(orders))
        else:
            self.attached_orders = []

    def __pay(self, actor):
        self.update_total()
        transaction = Transaction(
            amount=-self.total_krw,
            customer=self.user,
            user=actor
        )
        self.transaction = transaction
        db.session.add(transaction)

    def delete(self):
        for suborder in self.suborders:
            suborder.delete()
        super().delete()

    @classmethod
    def get_filter(cls, base_filter, column, filter_value):
        from app.payments.models.payment_method import PaymentMethod
        from app.models.user import User
        part_filter = f'%{filter_value}%'
        return \
            base_filter.filter(column.has(PaymentMethod.name.like(part_filter))) \
                if column.key == 'payment_method' else \
            base_filter.filter(column.has(Shipping.name.like(part_filter))) \
                if column.key == 'shipping' else \
            base_filter.filter(column.has(User.username.like(part_filter))) \
                if column.key == 'user' else \
            base_filter.filter(column.like(f'%{filter_value}%'))

    def is_editable(self):
        return self.status in [OrderStatus.pending, OrderStatus.can_be_paid]

    def to_dict(self, details=False):
        is_order_updated = False
        if not self.total_krw:
            self.update_total()
            is_order_updated = True
        if not self.total_rur:
            self.total_rur = self.total_krw * Currency.query.get('RUR').rate
            is_order_updated = True
        if not self.total_usd:
            self.total_usd = self.total_krw * Currency.query.get('USD').rate
            is_order_updated = True
        if is_order_updated:
            db.session.commit()
        result = {
            'id': self.id,
            'user': self.user.username if self.user else None,
            'customer_name': self.customer_name,
            'address': self.address,
            'phone': self.phone,
            'comment': self.comment,
            'invoice_id': self.invoice_id,
            'subtotal_krw': self.subtotal_krw,
            'total_weight': self.total_weight,
            'shipping_krw': self.shipping_krw,
            'total': self.total_krw,
            'total_krw': self.total_krw,
            'total_rur': float(self.total_rur),
            'total_usd': float(self.total_usd),
            'country': self.country.to_dict() if self.country else None,
            'zip': self.zip,
            'shipping': self.shipping.to_dict() if self.shipping else None,
            'status': self.status.name if self.status else None,
            'payment_method': self.payment_method.name \
                if self.payment_method else None,
            'tracking_id': self.tracking_id if self.tracking_id else None,
            'tracking_url': self.tracking_url if self.tracking_url else None,
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d %H:%M:%S') \
                if self.purchase_date else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
        if details:
            result = { **result,
                'suborders': [so.to_dict() for so in self.suborders],
                'order_products': [op.to_dict() for op in self.order_products],
                'attached_orders': [o.to_dict() for o in self.attached_orders]
            }
        return result

    def update_total(self):
        '''
        Updates totals of the order
        '''
        for suborder in self.suborders:
            suborder.update_total()

        if self.shipping is None:
            if self.shipping_method_id is not None:
                self.shipping = Shipping.query.get(self.shipping_method_id)
            else:
                self.shipping = NoShipping.query.first()
                if self.shipping is None:
                    self.shipping = NoShipping()
        self.total_weight = reduce(lambda acc, sub: acc + sub.total_weight,
                                   self.suborders, 0) + \
                            reduce(lambda acc, ao: acc + ao.total_weight, 
                                   self.attached_orders, 0)
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


    def get_order_excel(self):
        if len(self.order_products) == 0:
            raise OrderError("The order has no products")
        self.update_total()
        package_path = os.path.dirname(__file__) + '/..'
        suborder_fill = PatternFill(
            start_color='00FFFF00', end_color='00FFFF00', fill_type='solid')
        order_wb = openpyxl.open(f'{package_path}/templates/order_template.xlsx')
        ws = order_wb.worksheets[0]

        # Set order header
        ws.cell(2, 2, self.id)
        ws.cell(2, 3, self.when_created.strftime('%Y-%m-%d'))
        ws.cell(4, 2, self.customer_name)
        ws.cell(5, 2, str(self.address) + '\n' + str(self.zip))
        ws.cell(6, 2, self.phone)
        # Set currency rates
        ws.cell(8, 5, float(1 / Currency.query.get('RUR').rate))
        ws.cell(9, 5, float(1 / Currency.query.get('USD').rate))

        ws.cell(6, 6, self.subtotal_krw)
        ws.cell(6, 7, self.total_weight + self.shipping_box_weight)
        ws.cell(6, 8, self.shipping_krw)
        ws.cell(6, 9, self.total_krw)
        ws.cell(6, 13, reduce(lambda acc, op: acc + op.product.points, 
                              self.order_products, 0))
        # Set shipping
        ws.cell(1, 6, self.shipping.name)
        ws.cell(2, 6, self.country.name)
        # Set packaging
        ws.cell(11, 7, self.shipping_box_weight)

        # Set order product lines
        op_shipping = {}
        row = 11
        for suborder in self.suborders:
            if suborder.order_products.count() == 0:
                continue
            row += 1
            suborder_row = row
            ws.merge_cells(f"B{row}:C{row}")
            for cell in ws[f'A{row}:M{row}'][0]:
                cell.fill = suborder_fill
            ws.cell(row, 2, f'{suborder.subcustomer.username}: {suborder.subcustomer.name}')
            ws.cell(row, 6, suborder.total_krw)
            ws.cell(row, 7, suborder.total_weight)
            # ws.cell(row, 8, suborder_shipping)
            ws.cell(row, 9, f'=F{row} + H{row}')
            ws.cell(row, 10, f'=I{row} / $E$8')
            ws.cell(row, 11, f'=I{row} / $E$9')
            ws.cell(row, 13,
                reduce(
                    lambda acc, op: acc + op.product.points * op.quantity,
                    suborder.order_products, 0)
            )
            for op in suborder.order_products:
                row += 1
                op_shipping[row] = round(self.shipping_krw / self.total_weight * \
                    op.product.weight * op.quantity)
                ws.cell(row, 1, op.product_id)
                ws.cell(row, 2, op.product.name_english)
                ws.cell(row, 3, op.product.name_russian)
                ws.cell(row, 4, op.quantity)
                ws.cell(row, 5, op.price)
                ws.cell(row, 6, op.price * op.quantity)
                ws.cell(row, 7, op.product.weight * op.quantity)
                ws.cell(row, 8, op_shipping[row])
                ws.cell(row, 9, ws.cell(row, 6).value + ws.cell(row, 8).value)
                ws.cell(row, 10, f'=I{row} / $E$8')
                ws.cell(row, 11, f'=I{row} / $E$9')
                ws.cell(row, 12, op.product.points)
                ws.cell(row, 13, op.product.points * op.quantity)
            if suborder.local_shipping != 0:
                row += 1
                ws.cell(row, 2, "Local shipping")
                ws.cell(row, 4, 1)
                ws.cell(row, 5, 2500)
                ws.cell(row, 6, 2500)
            ws.cell(suborder_row, 8, f'=SUM(H{suborder_row + 1}:H{row})')
        # Compensate rounding error
        if len(op_shipping) > 0:
            diff = self.shipping_krw - \
                reduce(lambda acc, op_ship: acc + op_ship[1], op_shipping.items(), 0)
            if op_shipping.get(row) is None:
                row -= 1
            ws.cell(row, 8).value += diff
            ws.cell(row, 9).value += diff
        
        file = NamedTemporaryFile()
        order_wb.save(file.name)
        file.seek(0)
        return file
