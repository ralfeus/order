''' Represents purchase order '''
from datetime import datetime, date
import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text
from sqlalchemy import select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.models.base import BaseModel
from app.orders.models import Suborder

class PurchaseOrderStatus(enum.Enum):
    pending = 1
    partially_posted = 2
    posted = 3
    paid = 4
    payment_past_due = 5
    shipped = 6
    delivered = 7
    failed = 8
    cancelled = 9

class PurchaseOrder(db.Model, BaseModel):
    __tablename__ = 'purchase_orders'

    ''' Represents purchase order '''
    id = Column(String(23), primary_key=True, nullable=False)
    vendor_po_id = Column(String(12))
    suborder_id = Column(String(20), ForeignKey('suborders.id'), nullable=False)
    suborder = relationship('Suborder', foreign_keys=[suborder_id], lazy='joined')
    customer_id = Column(Integer, ForeignKey('subcustomers.id'))
    customer = relationship('Subcustomer', foreign_keys=[customer_id])
    contact_phone = Column(String(13))
    payment_phone = Column(String(13))
    payment_account = Column(String(32))
    status = Column(Enum(PurchaseOrderStatus))
    zip = Column(String(5))
    address_1 = Column(String(64))
    address_2 = Column(String(64))
    company_id = Column(Integer, ForeignKey('companies.id'))
    company = relationship('Company', foreign_keys=[company_id])
    vendor = Column(String(64))
    status_details = Column(Text)


    def __init__(self, suborder: Suborder, **kwargs):
        if len(suborder.id) > 5:
            self.id = 'PO-{}'.format(suborder.id[4:])
        else:
            self.id = 'PO-{}-{}'.format(suborder.order_id[4:], suborder.id)
        self.suborder = suborder

        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])
        # Here properties are set (attributes start with '__')

    @property
    def order_products(self) -> list:
        return self.suborder.get_order_products()

    @property
    def purchase_date(self) -> date:
        return self.suborder.buyout_date.date() \
            if self.suborder and self.suborder.buyout_date \
            else None

    @purchase_date.setter
    def purchase_date(self, value):
        if isinstance(value, datetime):
            self.suborder.buyout_date = value
        elif isinstance(value, str):
            self.suborder.buyout_date = datetime.strptime(value, '%Y-%m-%d')
        else:
            raise AttributeError('Unsupported value type for purchase_date: %s' % type(value))

    # @classmethod
    # @purchase_date.expression
    # def purchase_date(cls):
    #     return Suborder.buyout_date

    @property
    def address(self):
        return {'zip': self.zip, 'address_1': self.address_1, 'address_2': self.address_2}

    @property
    def bank_id(self):
        return self.company.bank_id

    def __repr__(self):
        return "<PurchaseOrder: {}>".format(self.id)

    @classmethod
    def get_filter(cls, base_filter, column, filter_value):
        from app.orders.models.subcustomer import Subcustomer
        from app.orders.models.suborder import Suborder
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
                    Suborder.buyout_date == filter_value)) \
                    if column == 'purchase_date' \
                else base_filter
        return base_filter

    def is_editable(self):
        return self.status in [PurchaseOrderStatus.pending, PurchaseOrderStatus.failed,
                               PurchaseOrderStatus.payment_past_due, PurchaseOrderStatus.cancelled]
                        
    def reset_status(self):
        self.status = PurchaseOrderStatus.pending
        self.status_details = None
        self.payment_account = None
        self.vendor_po_id = None

    def to_dict(self):
        purchase_date = self.purchase_date
        return {
            'id': self.id,
            'order_id': self.suborder.order_id,
            'vendor_po_id': self.vendor_po_id,
            'suborder_id': self.suborder_id,
            'customer_id': self.customer_id,
            'customer': self.customer.to_dict() if self.customer else None,
            'total_krw': self.suborder.total_krw,
            'address': self.address,
            'payment_account': self.payment_account,
            'status': self.status.name if self.status else None,
            'status_details': self.status_details,
            'vendor': self.vendor,
            'purchase_date': purchase_date.strftime('%Y-%m-%d') if purchase_date else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else None
        }

    # @classmethod
    # def from_dict(cls, attr):
    #     result = super().from_dict(attr)
    #     if result is None:
    #         if attr == 'purchase_date':
    #             return PurchaseOrder.purchase_date
    #         return None

    #     return result
