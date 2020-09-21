from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db

class OrderProductStatusEntry(db.Model):
    '''
    History of all changes of the product status change history
    '''
    __tablename__ = 'order_product_status_history'

    order_product_id = Column(Integer, ForeignKey('order_products.id'), primary_key=True)
    set_by = relationship('User')
    set_at = Column(DateTime, primary_key=True)
    status = Column(String(16))
    user_id = Column(Integer, ForeignKey('users.id'))

    def __repr__(self):
        return f"<OrderProduct {self.order_product_id} \"{self.status}\" set {self.set_at}>"
