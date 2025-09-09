''' Represents purchase order '''
from functools import reduce
from app.models.address import Address
from datetime import datetime, date
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, \
    String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.models.base import BaseModel
import app.orders.models as o
from app.orders.models.subcustomer import Subcustomer
import app.orders.models.suborder as so
from .company import Company

class PurchaseOrderStatus(enum.Enum):
    ''' Represents statuses of the purchase order '''
    pending = 1
    partially_posted = 2
    posted = 3
    paid = 4
    payment_past_due = 5
    shipped = 6
    delivered = 7
    failed = 8
    cancelled = 9

class PurchaseOrder(db.Model, BaseModel): #type: ignore
    ''' Represents purchase order '''
    __tablename__ = 'purchase_orders'

    id = Column(String(23), primary_key=True, nullable=False)
    vendor_po_id = Column(String(18))
    suborder_id = Column(String(20), ForeignKey('suborders.id'), nullable=False)
    suborder: 'so.Suborder' = relationship('Suborder', foreign_keys=[suborder_id], lazy='joined')
    customer_id = Column(Integer, ForeignKey('subcustomers.id'))
    customer: 'Subcustomer' = relationship('Subcustomer', foreign_keys=[customer_id])
    contact_phone = Column(String(13))
    payment_phone = Column(String(13))
    payment_account = Column(String(32))
    status = Column(Enum(PurchaseOrderStatus))
    address_id = Column(Integer, ForeignKey('addresses.id'))
    address: Address = relationship(Address, foreign_keys=[address_id])
    zip = Column(String(5))
    address_1 = Column(String(64))
    address_2 = Column(String(64))
    company_id = Column(Integer, ForeignKey('companies.id'))
    company: Company = relationship(Company, foreign_keys=[company_id])
    vendor = Column(String(64))
    purchase_restricted_products = Column(Boolean, default=False)
    status_details = Column(Text)
    when_posted = Column(DateTime)
    total_krw = Column(Integer)


    def __init__(self, suborder: 'so.Suborder', **kwargs):
        super().__init__(**kwargs)
        if len(suborder.id) > 5:
            self.id = 'PO-{}'.format(suborder.id[4:])
        else:
            self.id = 'PO-{}-{}'.format(suborder.order_id[4:], suborder.id)
        self.suborder = suborder
        self.total_krw = suborder.get_subtotal()
        # Here properties are set (attributes start with '__')

    @property
    def order_products(self) -> list:
        return self.suborder.get_order_products()

    @property
    def purchase_date(self) -> date:
        return self.suborder.buyout_date.date() \
            if self.suborder and self.suborder.buyout_date \
            else None #type: ignore

    @purchase_date.setter
    def purchase_date(self, value):
        if isinstance(value, datetime) or value is None:
            self.suborder.buyout_date = value
        elif isinstance(value, str):
            self.suborder.buyout_date = datetime.strptime(value, '%Y-%m-%d')
        else:
            raise AttributeError('Unsupported value type for purchase_date: %s' % type(value))

    # @classmethod
    # @purchase_date.expression
    # def purchase_date(cls):
    #     return Suborder.buyout_date

    # @property
    # def address(self):
    #     return {'zip': self.zip, 'address_1': self.address_1, 'address_2': self.address_2}

    @property
    def bank_id(self):
        return self.company.bank_id

    def __repr__(self):
        return "<PurchaseOrder: {}>".format(self.id)

    @classmethod
    def get_filter(cls, base_filter, column=None, filter_value=None):
        if column is None or filter_value is None:
            return base_filter
        # from app.orders.models.subcustomer import Subcustomer
        part_filter = f'%{filter_value}%'
        if isinstance(column, InstrumentedAttribute):
            return \
                base_filter.filter(column.has(
                    Subcustomer.name.like(part_filter))) \
                    if column.key == 'customer' \
                else base_filter.filter(column.in_([PurchaseOrderStatus[status]
                                        for status in filter_value.split(',')])) \
                    if column.key == 'status' \
                else base_filter.filter(column.in_([vendor
                                        for vendor in filter_value.split(',')])) \
                    if column.key == 'vendor' \
                else base_filter.filter(column.like(part_filter))
        if isinstance(column, property):
            column = column.fget.__name__
            return \
                base_filter.filter(PurchaseOrder.suborder.has(
                    so.Suborder.buyout_date == filter_value)) \
                    if column == 'purchase_date' \
                else base_filter
        if isinstance(column, str):
            return \
                base_filter.filter(PurchaseOrder.customer.has(
                    Subcustomer.name.like(part_filter))) \
                    if column == 'customer.name' \
                    else base_filter
        return base_filter

    def is_editable(self):
        return self.status in [PurchaseOrderStatus.posted, PurchaseOrderStatus.pending, 
                               PurchaseOrderStatus.failed, 
                               PurchaseOrderStatus.payment_past_due, 
                               PurchaseOrderStatus.cancelled]
                        
    def reset_status(self):
        self.set_status(PurchaseOrderStatus.pending)
        self.status_details = None
        self.payment_account = None
        self.vendor_po_id = None

    def set_status(self, status):
        if isinstance(status, str):
            status = PurchaseOrderStatus[status.lower()]
        elif isinstance(status, int):
            status = PurchaseOrderStatus(status)
            
        self.status = status
        if status == PurchaseOrderStatus.delivered:
            from app.purchase.signals import purchase_order_delivered
            purchase_order_delivered.send(self)

    def to_dict(self):
        from app.settings.models.setting import Setting
        from app.purchase.signals import purchase_order_model_preparing
        purchase_date = self.purchase_date
        allow_purchase_restricted_products = (
            Setting.query.get('purchase.allow_purchase_restricted_products') is not None and 
            Setting.query.get('purchase.allow_purchase_restricted_products').value == '1'
        )
        purchase_restricted_products = self.purchase_restricted_products \
            if allow_purchase_restricted_products else None
        res = purchase_order_model_preparing.send(self)
        ext_model = reduce(lambda acc, i: {**acc, **i}, [i[1] for i in res], {})
        return {
            'id': self.id,
            'order_id': self.suborder.order_id,
            'vendor_po_id': self.vendor_po_id,
            'suborder_id': self.suborder_id,
            'customer_id': self.customer_id,
            'customer': self.customer.to_dict() if self.customer else None,
            'company': self.company.name,
            'total_krw': self.total_krw,
            'address': self.address.to_dict() if self.address else None,
            'payment_account': self.payment_account,
            'status': self.status.name if self.status else None,
            'status_details': self.status_details,
            'vendor': self.vendor,
            'purchase_restricted_products': purchase_restricted_products,
            'purchase_date': purchase_date.strftime('%Y-%m-%d') if purchase_date else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None,
            'when_posted': self.when_posted.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_posted else None,
            **ext_model
        }
