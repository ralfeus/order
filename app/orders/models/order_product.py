from datetime import datetime
import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel

class OrderProductStatus(enum.Enum):
    pending = 1
    po_created = 2
    unavailable = 3
    purchased = 4
    shipped = 5
    complete = 6
    cancelled = 7

class OrderProductStatusEntry(db.Model):
    __tablename__ = 'order_product_status_history'
    # __table_args__ = { 'extend_existing': True }

    order_product_id = Column('order_product_id', Integer,
        ForeignKey('order_products.id'), primary_key=True)
    status = Column('status', Enum(OrderProductStatus))
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


class OrderProduct(db.Model, BaseModel):
    '''
    Represents an ordered item of the order. Doesn't exist apart from order
    '''
    __tablename__ = 'order_products'

    # Keep for back compatibility, remove when not needed
    order_id = Column(String(16), ForeignKey('orders.id'))
    suborder_id = Column(String(20), ForeignKey('suborders.id'), nullable=False)
    suborder = relationship('Suborder', foreign_keys=[suborder_id])
    product_id = Column(String(16), ForeignKey('products.id'))
    product = relationship('Product')
    price = Column(Integer)
    quantity = Column(Integer)
    private_comment = Column(String(256))
    public_comment = Column(String(256))
    status = Column(Enum(OrderProductStatus),
        server_default=OrderProductStatus.pending.name)
    status_history = relationship("OrderProductStatusEntry", lazy='dynamic')

    def __repr__(self):
        return "<OrderProduct: Suborder: {}, Product: {}, Status: {}".format(
            self.suborder.id, self.product_id, self.status)
    
    def set_status(self, status, user):
        self.status = status
        db.session.add(OrderProductStatusEntry(
            order_product_id=self.id,
            status=status,
            user=user,
            when_created=datetime.now()
        ))
        if status == OrderProductStatus.cancelled:
            self.suborder.order.update_total()

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.suborder.order_id if self.suborder else self.order_id,
            'suborder_id': self.suborder_id,
            'order_product_id': self.id,
            'customer': self.suborder.order.name if self.suborder and self.suborder.order else None,
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
            'status': self.status.name if self.status else None,
            'weight': self.product.weight,
            'purchase': self.product.purchase,
            'when_created': self.when_created.strftime('%Y-%m-%d') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d') if self.when_changed else None
        }
