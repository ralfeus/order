from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.orders.models import Order
from app.models.base import BaseModel


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
    status = Column(String(16))
    status_history = relationship('OrderProductStatusEntry', backref="order_product",
                                  lazy='dynamic')

    def __repr__(self):
        return "<OrderProduct: Order: {}, Product: {}, Status: {}".format(
            self.order_id, self.product_id, self.status)

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
            'status': self.status,
            'weight': self.product.weight,
            'when_created': self.when_created.strftime('%Y-%m-%d') if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d') if self.when_changed else None
        }
