"""
Tests for Stripe payment method routes
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.payments.models.payment import Payment, PaymentStatus
from app.payments.models.payment_method import PaymentMethod
from app.users.models.role import Role
from app.users.models.user import User


STRIPE_PAYMENT_INTENT_ID = 'pi_test_123'


def _make_mock_intent(payment_id: int) -> MagicMock:
    """Return a mock Stripe PaymentIntent that looks like a successful charge."""
    intent = MagicMock()
    intent.status = 'succeeded'
    intent.metadata = {'payment_id': str(payment_id)}
    intent.latest_charge = None
    return intent


class TestStripePayments(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name="admin")
        self.user = User(
            username="user1_test_stripe",
            email="user1_test_stripe@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
        )
        self.admin = User(
            username="admin_test_stripe",
            email="admin_test_stripe@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
            roles=[admin_role],
        )
        usd_currency = Currency(code="USD", rate=0.5)
        payment_method = PaymentMethod(id=1)
        self.try_add_entities([
            self.user, self.admin, admin_role, usd_currency, payment_method
        ])

    def _make_payment(self, status: PaymentStatus) -> Payment:
        currency = Currency.query.get('USD')
        payment = Payment(
            user_id=self.user.id,  # type: ignore
            amount_sent_original=10,
            currency=currency,
            amount_sent_krw=20,
            amount_received_krw=10,
            status=status,
            when_created=datetime.now(),
            payment_method_id=1,
        )
        self.try_add_entities([payment])
        return payment

    def _call_success(self, payment_id: int) -> object:
        url = f'/payments/{payment_id}/stripe/success' \
              f'?payment_intent={STRIPE_PAYMENT_INTENT_ID}'
        return self.client.get(url)

    def test_stripe_success_approves_pending_payment(self):
        """Stripe success callback approves a payment that is in pending status."""
        payment = self._make_payment(PaymentStatus.pending)
        with patch('app.payments.routes.payment_methods.stripe.stripe.PaymentIntent.retrieve',
                   return_value=_make_mock_intent(payment.id)):
            self._call_success(payment.id)
        updated = Payment.query.get(payment.id)
        self.assertEqual(updated.status, PaymentStatus.approved)

    def test_stripe_success_does_not_change_approved_payment(self):
        """Stripe success callback leaves an already-approved payment unchanged."""
        payment = self._make_payment(PaymentStatus.approved)
        with patch('app.payments.routes.payment_methods.stripe.stripe.PaymentIntent.retrieve',
                   return_value=_make_mock_intent(payment.id)):
            self._call_success(payment.id)
        updated = Payment.query.get(payment.id)
        self.assertEqual(updated.status, PaymentStatus.approved)

    def test_stripe_success_does_not_approve_rejected_payment(self):
        """Stripe success callback does not approve a rejected payment."""
        payment = self._make_payment(PaymentStatus.rejected)
        with patch('app.payments.routes.payment_methods.stripe.stripe.PaymentIntent.retrieve',
                   return_value=_make_mock_intent(payment.id)):
            self._call_success(payment.id)
        updated = Payment.query.get(payment.id)
        self.assertEqual(updated.status, PaymentStatus.rejected)
