'''
Suborder model
Part of the order for single subcustomer
'''
from __future__ import annotations
from datetime import datetime
from functools import reduce
from typing import Optional

from flask import current_app

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.currencies.models.currency import Currency
from app.models.base import BaseModel
import app.orders.models.order as o
from app.products.models import Product

from .order_product import OrderProduct, OrderProductStatus

class Suborder(db.Model, BaseModel): #type: ignore
    ''' Suborder '''
    __tablename__ = 'suborders'
    __id_pattern = 'SOS-{order_num}-'

    id: str = Column(String(20), primary_key=True, nullable=False)
    seq_num: int = Column(Integer)
    subcustomer_id: int = Column(Integer, ForeignKey('subcustomers.id'))
    subcustomer = relationship("Subcustomer", foreign_keys=[subcustomer_id])
    order_id: str = Column(String(16), ForeignKey('orders.id', onupdate='CASCADE'), nullable=False)
    order: o.Order = relationship('Order', foreign_keys=[order_id])
    buyout_date: datetime = Column(DateTime, index=True)
    order_products = relationship('OrderProduct', lazy='dynamic', cascade='all, delete-orphan')
    local_shipping: int = Column(Integer(), default=0)

    def __init__(self, order=None, order_id=None, seq_num=None, **kwargs):
        if order:
            self.order = order
            order_id = order.id
        if not order_id:
            raise AttributeError("No order is referred")
        self.order_id = order_id

        prefix = self.__id_pattern.format(order_num=order_id[4:16])
        last_suborder = Suborder.query.filter_by(order_id=self.order_id).\
            order_by(Suborder.seq_num.desc()).first()
        self.seq_num = last_suborder.seq_num + 1 if last_suborder else 1
        self.id = prefix + '{:03d}'.format(int(self.seq_num))

        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])
        # Here properties are set (attributes start with '__')

    def __repr__(self):
        return "<Suborder: {}>".format(self.id)

    def get_total_weight(self):
        return reduce(
                lambda acc, op: acc + op.product.weight * op.quantity,
                self.get_order_products(), 0)

    # @property
    # def total_krw(self):
    #     return self.get_total_krw()

    def delete(self):
        for op in self.order_products:
            op.delete()
        super().delete()

    def get_order_products(self) -> list:
        return [op for op in self.order_products
                   if op.status != OrderProductStatus.unavailable]

    def get_subtotal(self, currency:Optional[Currency]=None) -> float:
        rate = 1 if currency is None else currency.get_rate(self.order.when_created)
        return reduce(
            lambda acc, op: acc + op.price * op.quantity,
            self.get_order_products(), 0) * rate

    def get_shipping(self, currency:Optional[Currency]=None, local_shipping=True) -> float:
        '''Returns shipping cost for a suborder, which is a proportional to its weight in total order.
        Provided in currency requested'''
        if self.order.total_weight == 0:
            return 0
        rate = 1 if currency is None else currency.get_rate(self.order.when_created)
        return self.get_weight() / self.order.total_weight \
            * float(self.order.get_shipping(currency)) + \
            (self.local_shipping * rate if local_shipping and self.local_shipping else 0)

    # def get_total_krw(self, local_shipping=True) -> int:
    #     return reduce(
    #         lambda acc, op: acc + op.price * op.quantity,
    #         self.get_order_products(), 0) + \
    #         (self.local_shipping if local_shipping and self.local_shipping else 0)

    def get_total(self, currency=None, local_shipping=True) -> float:
        if isinstance(currency, str):
            currency = Currency.query.get(currency)
        return float(self.get_subtotal(currency)) + \
            self.get_shipping(currency, local_shipping)

    def get_total_points(self):
        return reduce(
            lambda acc, op: acc + op.product.points * op.quantity, 
            self.get_order_products(), 0)

    def get_weight(self):
        return reduce(
            lambda acc, op: acc + op.product.weight * op.quantity,
            self.get_order_products(), 0)

    def is_for_internal(self):
        return self.subcustomer.is_internal()

    def get_purchase_order(self):
        from app.purchase.models import PurchaseOrder
        return PurchaseOrder.query.filter_by(suborder_id=self.id).first()

    def to_dict(self):
#        if not self.total_krw:
#            self.total_krw = reduce(lambda acc, op: acc + op.price * op.quantity, self.order_products, 0)
#        if not self.total_rur:
#            self.total_rur = self.total_krw * Currency.query.get('RUR').rate
#        if not self.total_usd:
#            self.total_usd = self.total_krw * Currency.query.get('USD').rate
        return {
            'id': self.id,
            'order_id': self.order_id,
            'seq_num': self.seq_num,
            'subcustomer': f"{self.subcustomer.username}, {self.subcustomer.name}, {self.subcustomer.password}" \
                if self.subcustomer else None,
            'buyout_date': self.buyout_date.strftime('%Y-%m-%d') if self.buyout_date else None,
            'order_products': [op.to_dict() for op in self.order_products],
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else None
        }

    def update_total(self):
        def calc_op_total(acc, op):
            return acc + op.price * op.quantity

        bulk_shipping_products = list(filter(
            lambda op: not op.product.separate_shipping,
            self.get_order_products()))
        free_local_shipment_eligibility_amount = reduce(
            calc_op_total, filter(
                lambda op: not op.product.separate_shipping,
                bulk_shipping_products
            ), 0)
        self.local_shipping = \
            0 if len(bulk_shipping_products) == 0 \
            else current_app.config['LOCAL_SHIPPING_COST'] \
                if free_local_shipment_eligibility_amount < \
                    current_app.config['FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD'] \
                else 0
        self.when_changed = datetime.now()
        # db.session.commit()

