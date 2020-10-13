''' Represents purchase order '''
import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db
from app.models.base import BaseModel
from app.orders.models import Suborder

class PurchaseOrderStatus(enum.Enum):
    pending = 1
    posted = 2
    paid = 3
    delivered = 4
    failed = 5

class PurchaseOrder(db.Model, BaseModel):
    __tablename__ = 'purchase_orders'

    ''' Represents purchase order '''
    id = Column(String(23), primary_key=True, nullable=False)
    suborder_id = Column(Integer, ForeignKey('suborders.id'))
    suborder = relationship('Suborder', foreign_keys=[suborder_id])
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


    def __init__(self, suborder: Suborder, **kwargs):
        self.id = '{}-{:06d}'.format(suborder.order_id, suborder.id)
        self.suborder = suborder

        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])
        # Here properties are set (attributes start with '__')

    @property
    def order_products(self):
        return self.suborder.order_products

    @property
    def purchase_date(self):
        return self.suborder.buyout_date

    @property
    def address(self):
        return {'zip': self.zip, 'address_1': self.address_1, 'address_2': self.address_2}

    def __repr__(self):
        return "<PurchaseOrder: {}>".format(self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.suborder.order_id,
            'suborder_id': self.suborder_id,
            'customer_id': self.customer_id,
            'customer': self.customer.name,
            'total_krw': self.suborder.total_krw,
            'address': self.address,
            'payment_account': self.payment_account,
            'status': self.status.name if self.status else None,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else None
        }
