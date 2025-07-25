''' Order product model'''
from __future__ import annotations
from datetime import datetime
import enum
from functools import reduce

from flask_security import current_user

from sqlalchemy import and_, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.models.base import BaseModel
from app.orders.signals import order_product_model_preparing
from app.products.models.product import Product
from app.shipping.models.shipping import PostponeShipping

from .order_status import OrderStatus

class OrderProductStatus(enum.Enum):
    pending = 1
    po_created = 2
    unavailable = 3
    purchased = 4
    shipped = 5
    # complete = 6
    # cancelled = 7

class OrderProductStatusEntry(db.Model): # type: ignore
    __tablename__ = 'order_product_status_history'
    __table_args__ = { 'extend_existing': True }

    order_product_id = Column('order_product_id', Integer,
        ForeignKey('order_products.id'), primary_key=True)
    order_product = relationship('OrderProduct', foreign_keys=[order_product_id])
    status = Column('status', Enum(OrderProductStatus),
        default=OrderProductStatus.pending)
    user_id = Column('user_id', Integer, ForeignKey('users.id'))
    user = relationship("User", foreign_keys=[user_id])
    when_created = Column('when_created', DateTime, primary_key=True)

    def to_dict(self):
        return {
            'status': self.status.name if self.status else None,
            'set_by': self.user.username if self.user else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None
        }


class OrderProduct(db.Model, BaseModel): # type: ignore
    '''
    Represents an ordered item of the order. Doesn't exist apart from order
    '''
    __tablename__ = 'order_products'

    # Keep for back compatibility, remove when not needed
    order_id = Column(String(16), ForeignKey('orders.id'))
    suborder_id = Column(String(20), ForeignKey('suborders.id', onupdate='CASCADE'),
        nullable=False)
    suborder = relationship('Suborder', foreign_keys=[suborder_id])
    product_id = Column(String(16), ForeignKey('products.id'))
    product: Product = relationship('Product')
    price = Column(Integer)
    quantity = Column(Integer)
    private_comment = Column(String(256))
    public_comment = Column(String(256))
    status = Column(Enum(OrderProductStatus), default=OrderProductStatus.pending)
    status_history = relationship("OrderProductStatusEntry", lazy='dynamic')

    def __init__(self, **kwargs):
        if not kwargs.get('product'):
            from app.products.models import Product
            kwargs['product'] = Product.query.get(kwargs['product_id'])
            if not kwargs['product']:
                raise AttributeError("Order product must refer to existing product")
        if not kwargs.get('price'):
            kwargs['price'] = kwargs['product'].price
        
        super().__init__(**kwargs)

    def __repr__(self):
        return "<OrderProduct: Suborder: {}, Product: {}, Status: {}".format(
            self.suborder.id, self.product_id, self.status)

    def delete(self):
        for op_status_entry in self.status_history:
            db.session.delete(op_status_entry)
        db.session.delete(self)

    @classmethod
    def get_filter(cls, base_filter, column=None, filter_value=None):
        if column is None or filter_value is None:
            return base_filter
        from .order import Order
        from .subcustomer import Subcustomer
        from .suborder import Suborder
        from app.products.models.product import Product
        part_filter = f'%{filter_value}%'
        if isinstance(column, InstrumentedAttribute):
            return \
                base_filter.filter(OrderProduct.suborder.has(
                    Suborder.order_id.like(part_filter))) \
                    if column.key == 'order_id' \
                else base_filter.filter(column.in_([OrderProductStatus[status]
                                        for status in filter_value.split(',')])) \
                    if column.key == 'status' \
                else base_filter.filter(column.has(Product.name_english.like(part_filter))) \
                    if column.key == 'product' \
                else base_filter.filter(column.like(part_filter))
        return \
            base_filter.filter(OrderProduct.suborder.has(
                Suborder.order.has(Order.customer_name.like(part_filter)))) \
                if column == 'customer' \
            else base_filter.filter(OrderProduct.suborder.has(
                Suborder.buyout_date == filter_value)) \
                if column == 'buyout_date' \
            else base_filter.filter(OrderProduct.suborder.has(Suborder.order.has(
                Order.status.in_([OrderStatus[status] 
                                 for status in filter_value.split(',')])))) \
                if column == 'order_status' \
            else base_filter.filter(OrderProduct.suborder.has(
                Suborder.subcustomer.has(Subcustomer.name.like(part_filter)))) \
                if column == 'subcustomer' \
            else base_filter

    def get_price(self, currency=None, rate: float=None):
        if rate is None:
            rate = currency.get_rate(self.suborder.order.when_created) \
                if currency is not None else 1
        return self.price * rate

    def need_to_update_total(self, payload):
        return len({'product_id', 'product', 'price', 'quantity'} &
                   set(payload.keys())) > 0 

    def postpone(self):
        from .order import Order
        from .suborder import Suborder
        postponed_order = Order.query.join(PostponeShipping).filter(and_(
            Order.user_id == self.suborder.order.user_id,
            Order.status.in_([OrderStatus.pending, OrderStatus.can_be_paid])
        )).order_by(Order.when_created.desc()).first()
        referred_order = self.suborder.order
        if not postponed_order:
            postponed_order = Order(
                user=referred_order.user,
                customer_name=referred_order.customer_name,
                address=referred_order.address,
                country=referred_order.country,
                phone=referred_order.phone,
                comment="Postponed due to products unavailability",
                shipping=PostponeShipping.query.first(),
                when_created=datetime.now(),
            )
            db.session.add(postponed_order)
        suborder = postponed_order.suborders.filter_by(
            subcustomer=self.suborder.subcustomer).first()
        if not suborder:
            suborder = Suborder(
                order=postponed_order,
                subcustomer=self.suborder.subcustomer)
            db.session.add(suborder)
        postponed_order_product = OrderProduct(
            suborder=suborder,
            product=self.product,
            price=self.price,
            quantity=self.quantity,
            private_comment=self.private_comment,
            public_comment=self.public_comment
        )
        db.session.add(postponed_order_product)
        postponed_order.update_total()
        self.delete()
        return postponed_order_product
    
    def set_status(self, status, user=None):
        self.status = status
        db.session.add(OrderProductStatusEntry(
            order_product=self,
            status=status,
            user=user \
                if user is not None else \
                None if current_user.is_anonymous else \
                current_user,
            when_created=datetime.now()
        ))
        if status == OrderProductStatus.unavailable:
            self.suborder.order.update_total()

    def to_dict(self):
        res = order_product_model_preparing.send(self)
        ext_model = reduce(lambda acc, i: {**acc, **i}, [i[1] for i in res], {})
        return {
            'id': self.id,
            'order_id': self.suborder.order_id if self.suborder else self.order_id,
            'suborder_id': self.suborder_id,
            'customer': self.suborder.order.customer_name if self.suborder and self.suborder.order else None,
            'subcustomer_id': self.suborder.subcustomer_id if self.suborder else None,
            'subcustomer': self.suborder.subcustomer.name if self.suborder and self.suborder.subcustomer else None,
            'buyout_date': self.suborder.buyout_date.strftime('%Y-%m-%d') if self.suborder and self.suborder.buyout_date else None,
            'product_id': self.product_id,
            'product': self.product.name_english,
            'name': self.product.name,
            'name_english': self.product.name_english,
            'name_russian': self.product.name_russian,
            'private_comment': self.private_comment,
            'public_comment': self.public_comment,
            'price': self.price,
            'points': self.product.points,
            # 'comment': self.order.comment,
            'quantity': self.quantity,
            'order_status': self.suborder.order.status.name,
            'status': self.status.name if self.status else None,
            'weight': self.product.weight,
            'purchase': self.product.purchase,
            'available': self.product.available,
            'color': self.product.color,
            'when_created': self.when_created.strftime('%Y-%m-%d') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d') if self.when_changed else None,
            **ext_model
        }
