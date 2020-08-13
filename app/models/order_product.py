from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db


class OrderProduct(db.Model):
    '''
    Represents an ordered item of the order. Doesn't exist apart from order
    '''
    __tablename__ = 'order_products'

    id = Column(Integer, primary_key=True)
    order_id = Column(String(16), ForeignKey('orders.id'))
    product_id = Column(String(16), ForeignKey('products.id'))
    product = relationship('Product')
    price = Column(Integer)
    quantity = Column(Integer)
    subcustomer = Column(String(256))
    private_comment = Column(String(256))
    public_comment = Column(String(256))
    status = Column(String(16))
    status_history = relationship('OrderProductStatusEntry', backref="order_product", lazy='dynamic')
    changed_at = Column(DateTime, index=True)

    def __repr__(self):
        return "<OrderProduct: Order: {}, Product: {}, Status: {}".format(
            self.order_id, self.product_id, self.status)
    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'order_product_id': self.id,
            'customer': self.order.name,
            'subcustomer': self.subcustomer,
            'product_id': self.product_id,
            'product': self.product.name_english,
            'private_comment': self.private_comment,
            'public_comment': self.public_comment,
            'price': self.price,
            'comment': self.order.comment,
            'quantity': self.quantity,
            'status': self.status
        }