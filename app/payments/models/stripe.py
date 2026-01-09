import stripe
from app import app
from .payment import Payment
from .payment_method import PaymentMethod


class Stripe(PaymentMethod):
    __mapper_args__ = {'polymorphic_identity': 'stripe'}
    
    def __init__(self):
        self.name = 'Stripe'

    def execute_payment(self, payment: Payment):
        """Return custom checkout URL instead of Checkout Session"""
        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        return {'url': f'{payment.id}/stripe/checkout'}