from datetime import datetime
import enum
from functools import reduce

from sqlalchemy import Column, Enum, Numeric, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app import db
from app.exceptions import PaymentNoReceivedAmountException
from app.models.base import BaseModel
from app.orders.models.order import OrderStatus
from app.payments.models.transaction import Transaction

payments_orders = db.Table('payments_orders',
        db.Column('payment_id', db.Integer(), db.ForeignKey('payments.id')),
        db.Column('order_id', db.String(16), db.ForeignKey('orders.id')))

payments_files = db.Table('payments_files',
    db.Column('payment_id', db.Integer(), db.ForeignKey('payments.id')),
    db.Column('file_id', db.Integer(), db.ForeignKey('files.id')))

class PaymentStatus(enum.Enum):
    pending = 1
    approved = 2
    rejected = 3
    cancelled = 4

class Payment(db.Model, BaseModel):
    '''
    Customer's payment
    '''
    __tablename__ = 'payments'

    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', foreign_keys=[user_id])
    orders = db.relationship('Order', secondary=payments_orders,
                             backref=db.backref('payments', lazy='dynamic'),
                             lazy='dynamic')
    currency_code = Column(String(3), ForeignKey('currencies.code'))
    currency = relationship('Currency')
    amount_sent_original = Column(Numeric(scale=2), default=0)
    amount_sent_krw = Column(Integer, default=0)
    amount_received_krw = Column(Integer, default=0)
    payment_method_id = Column(Integer, ForeignKey('payment_methods.id'))
    payment_method = relationship("PaymentMethod", foreign_keys=[payment_method_id])
    evidences = relationship("File", secondary=payments_files, lazy='dynamic')
    status = Column('status', Enum(PaymentStatus),
        server_default=PaymentStatus.pending.name)
    transaction_id = Column(Integer(), ForeignKey('transactions.id'))
    transaction = relationship("Transaction", foreign_keys=[transaction_id])
    changed_by_id = Column(Integer, ForeignKey('users.id'))
    changed_by = relationship('User', foreign_keys=[changed_by_id])
    additional_info = Column(Text)

    def is_editable(self):
        return self.status != PaymentStatus.approved

    def set_status(self, value, messages):
        if isinstance(value, str):
            value = PaymentStatus[value]
        elif isinstance(value, int):
            value = PaymentStatus(value)

        self.status = value
        self.when_changed = datetime.now()

        if value == PaymentStatus.approved:
            if not self.amount_received_krw:
                raise PaymentNoReceivedAmountException(
                    f"No received amount is set for payment <{self.id}>")

            self.add_payment(messages)

    def add_payment(self, messages):
        transaction = Transaction(
            amount=self.amount_received_krw,
            customer=self.user,
            user=self.changed_by
        )
        db.session.add(transaction)
        self.transaction = transaction

        self.update_orders(messages)

    def update_orders(self, messages):
        total_orders_amount = reduce(
            lambda acc, o: acc + o.total_krw,
            self.orders.filter_by(status=OrderStatus.pending), 0
        )
        if self.amount_received_krw >= total_orders_amount:
            for order in self.orders:
                order.payment_method_id = self.payment_method_id
                if order.status == OrderStatus.pending:
                    order.set_status(OrderStatus.can_be_paid, actor=self.changed_by)
                    messages.append(f"Order <{order.id}> status is set to CAN_BE_PAID")

    def to_dict(self):
        '''
        Get representation of the payment as dictionary for JSON conversion
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
            'amount_sent_original': float(self.amount_sent_original),
            'amount_sent_original_string': self.currency.format(self.amount_sent_original),
            'amount_krw': self.amount_sent_krw or 0,
            'amount_sent_krw': self.amount_sent_krw or 0,
            'amount_received_krw': self.amount_received_krw or 0,
            'currency_code': self.currency.code,
            'payment_method': self.payment_method.to_dict() if self.payment_method else None,
            # 'payee': self.payment_method.payee.to_dict() \
            #     if self.payment_method and self.payment_method.payee else None,
            'evidences': [{**evidence.to_dict(), **{'url': '/' + evidence.path}} 
                          for evidence in self.evidences],
            'additional_info': self.additional_info,
            'status': self.status.name,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
