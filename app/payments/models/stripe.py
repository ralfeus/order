from app.payments.models.payment import Payment
from app.payments.models.payment_method import PaymentMethod


class Stripe(PaymentMethod):
    __mapper_args__ = {'polymorphic_identity': 'stripe'}
    
    def __init__(self):
        self.name = 'Stripe'

    def execute_payment(self, payment: Payment):
        """Return custom checkout URL instead of Checkout Session"""
        return {'url': f'{payment.id}/stripe/checkout'}