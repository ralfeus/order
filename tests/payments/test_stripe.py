"""
Tests for Stripe payment method routes
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.payments.models.payment import Payment, PaymentStatus
from app.payments.models.payment_method import PaymentMethod
from app.payments.routes.payment_methods.stripe import FeeStructure, calculate_service_fee
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

    def test_create_payment_intent_amount_not_less_than_base_amount(self):
        """Amount sent to Stripe must be no less than the original payment amount.

        When FX rate adjustments cause the calculated total to fall below the
        original amount_sent_original, the endpoint must align up to the
        original before creating the PaymentIntent.
        """
        payment = self._make_payment(PaymentStatus.pending)

        # Simulate a fee structure where calculated total < amount_sent_original (10 USD)
        low_fee_structure = FeeStructure(send_to_stripe=5.0)

        mock_customers = MagicMock()
        mock_customers.is_empty = True
        mock_customer = MagicMock()
        mock_customer.id = 'cus_test_123'

        mock_intent = MagicMock()
        mock_intent.client_secret = 'pi_secret_test'
        mock_intent.id = 'pi_test_456'

        stripe_create = MagicMock(return_value=mock_intent)

        with patch('app.payments.routes.payment_methods.stripe.calculate_base_amount',
                   return_value=5.0), \
             patch('app.payments.routes.payment_methods.stripe.calculate_service_fee',
                   return_value=low_fee_structure), \
             patch('app.payments.routes.payment_methods.stripe.stripe.Customer.search',
                   return_value=mock_customers), \
             patch('app.payments.routes.payment_methods.stripe.stripe.Customer.create',
                   return_value=mock_customer), \
             patch('app.payments.routes.payment_methods.stripe.stripe.PaymentIntent.create',
                   stripe_create):
            response = self.client.post(
                '/api/v1/payment/stripe/create-payment-intent',
                json={'payment_id': payment.id, 'payment_method_id': 'pm_test_123'}
            )

        self.assertEqual(response.status_code, 200)
        stripe_create.assert_called_once()
        amount_charged = stripe_create.call_args[1]['amount']
        # amount_sent_original=10 USD → minimum 1000 cents
        self.assertGreaterEqual(
            amount_charged,
            int(float(payment.amount_sent_original) * 100),
            f"Stripe was charged {amount_charged} cents, which is less than "
            f"the original {int(float(payment.amount_sent_original) * 100)} cents"
        )

    def test_fee_eur_total_is_5_percent(self):
        """EUR fee: send_to_stripe should be base_amount * 1.05 (rounded up to cent)."""
        import math
        base = 100.0
        fees = calculate_service_fee(base, 'EUR')
        expected = math.ceil(base * 1.05 * 100) / 100
        self.assertAlmostEqual(fees.send_to_stripe, expected, places=2)
        self.assertAlmostEqual(fees.total_service_fee, fees.send_to_stripe - base, places=2)

    def test_fee_usd_total_is_6_percent(self):
        """USD fee: send_to_stripe should be base_amount * 1.06 (rounded up to cent)."""
        import math
        base = 100.0
        fees = calculate_service_fee(base, 'USD')
        expected = math.ceil(base * 1.06 * 100) / 100
        self.assertAlmostEqual(fees.send_to_stripe, expected, places=2)
        self.assertAlmostEqual(fees.total_service_fee, fees.send_to_stripe - base, places=2)

    def test_fee_eur_no_stripe_wise_fee(self):
        """EUR fee: no stripe-wise component."""
        fees = calculate_service_fee(100.0, 'EUR')
        self.assertEqual(fees.stripe_wise_fee, 0)
        self.assertEqual(fees.send_to_wise, fees.send_to_bank)

    def test_fee_usd_has_stripe_wise_fee(self):
        """USD fee: stripe-wise component is non-zero."""
        fees = calculate_service_fee(100.0, 'USD')
        self.assertGreater(fees.stripe_wise_fee, 0)

    def test_fee_service_fee_is_2_percent(self):
        """service_fee is always 2% of base_amount for both currencies."""
        import math
        base = 100.0
        for currency in ('EUR', 'USD'):
            with self.subTest(currency=currency):
                fees = calculate_service_fee(base, currency)
                expected = math.ceil(base * 0.02 * 100) / 100
                self.assertAlmostEqual(fees.service_fee, expected, places=2)
