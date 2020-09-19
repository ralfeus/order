from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel


class OrderProduct(db.Model, BaseModel):
    '''
    Represents an ordered item of the order. Doesn't exist apart from order
    '''
    __tablename__ = 'order_products'

    # Keep for back compatibility, remove when not needed
    order_id = Column(String(16), ForeignKey('orders.id')) 
    suborder_id = Column(Integer, ForeignKey('suborders.id'))
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
            'subcustomer': self.suborder.subcustomer.name if self.suborder and self.suborder.subcustomer else None,
            'buyout_date': self.suborder.buyout_date.strftime('%Y-%m-%d') if self.suborder and self.suborder.buyout_date else None,
            'product_id': self.product_id,
            'product': self.product.name_english,
            'private_comment': self.private_comment,
            'public_comment': self.public_comment,
            'price': self.price,
            #'comment': self.order.comment,
            'quantity': self.quantity,
            'status': self.status
        }
