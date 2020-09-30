import enum
from sqlalchemy import Column, DateTime, Enum, Numeric, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app import db
from app.models.base import BaseModel

transactions_orders = db.Table('transactions_orders',
        db.Column('transaction_id', db.Integer(), db.ForeignKey('transactions.id')),
        db.Column('order_id', db.String(16), db.ForeignKey('orders.id')))

class TransactionStatus(enum.Enum):
    pending = 1
    approved = 2
    rejected = 3
    cancelled = 4

class Transaction(db.Model, BaseModel):
    '''
    Customer wallet's transaction
    '''
    __tablename__ = 'transactions'

    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    orders = db.relationship('Order', secondary=transactions_orders,
                             backref=db.backref('transactions', lazy='dynamic'))
    currency_code = Column(String(3), ForeignKey('currencies.code'))
    currency = relationship('Currency')
    amount_sent_original = Column(Numeric(scale=2))
    amount_sent_krw = Column(Integer)
    amount_received_krw = Column(Integer)
    payment_method = Column(String(16))
    proof_image = Column(String(256))
    __status = Column('status', Enum(TransactionStatus))
    changed_by_id = Column(Integer, ForeignKey('users.id'))
    changed_by = relationship('User', foreign_keys=[changed_by_id])

    @property
    def status(self):
        return self.__status

    @status.setter
    def status(self, value):
        if isinstance(value, str):
            value = TransactionStatus[value]
        elif isinstance(value, int):
            value = TransactionStatus(value)

        self.__status = value


    def to_dict(self):
        '''
        Get representation of the transaction as dictionary for JSON conversion
        '''
        if not self.amount_sent_original:
            self.amount_sent_original = 0
            db.session.commit()
        return {
            'id': self.id,
            'orders': [order.id for order in self.orders],
            'user_id': self.user_id,
            'user_name': self.user.username,
            'amount_original': float(self.amount_sent_original),
            'amount_original_string': self.currency.format(self.amount_sent_original),
            'amount_krw': self.amount_sent_krw,
            'amount_received_krw': self.amount_received_krw,
            'currency_code': self.currency.code,
            'payment_method': self.payment_method,
            'evidence_image': self.proof_image,
            'status': self.status.name,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') if self.when_created else '',
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') if self.when_changed else ''
        }
