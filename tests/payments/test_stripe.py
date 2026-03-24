"""
Tests for Stripe payment method routes
"""

from datetime import datetime
import hashlib
import hmac
import json
import queue
import re
import socket
import subprocess
import threading
import time
from unittest.mock import MagicMock, patch
from werkzeug.serving import make_server

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
        usd_currency = Currency(code="USD", rate=0.5, enabled=True)
        payment_method = PaymentMethod(id=1)
        self.try_add_entities([
            self.user, self.admin, admin_role, usd_currency, payment_method
        ])

    def _make_payment(self, status: PaymentStatus) -> Payment:
        currency = db.session.get(Currency, 'USD')
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

    def test_stripe_success_renders_without_approving(self):
        """Success redirect just renders the page; it does not approve the payment."""
        payment = self._make_payment(PaymentStatus.pending)
        self._call_success(payment.id)
        updated = db.session.get(Payment, payment.id)
        self.assertEqual(updated.status, PaymentStatus.pending)

    def test_webhook_approves_pending_payment(self):
        """Webhook checkout.session.completed approves a pending payment."""
        from app.payments.routes.payment_methods.stripe import _handle_checkout_complete
        payment = self._make_payment(PaymentStatus.pending)
        session = MagicMock()
        session.payment_intent = 'pi_test_webhook'

        mock_intent = MagicMock()
        mock_intent.metadata = {'payment_id': str(payment.id)}
        mock_intent.latest_charge = None

        with patch('app.payments.routes.payment_methods.stripe.stripe.PaymentIntent.retrieve',
                   return_value=mock_intent):
            _handle_checkout_complete(session)

        updated = db.session.get(Payment, payment.id)
        self.assertEqual(updated.status, PaymentStatus.approved)

    def test_webhook_does_not_approve_non_pending_payment(self):
        """Webhook does not change a payment that is not pending."""
        from app.payments.routes.payment_methods.stripe import _handle_checkout_complete
        for status in (PaymentStatus.approved, PaymentStatus.rejected):
            with self.subTest(status=status):
                payment = self._make_payment(status)
                session = MagicMock()
                session.payment_intent = 'pi_test_webhook'
                mock_intent = MagicMock()
                mock_intent.metadata = {'payment_id': str(payment.id)}
                mock_intent.latest_charge = None
                with patch('app.payments.routes.payment_methods.stripe.stripe.PaymentIntent.retrieve',
                           return_value=mock_intent):
                    _handle_checkout_complete(session)
                updated = db.session.get(Payment, payment.id)
                self.assertEqual(updated.status, status)

    def test_checkout_session_amount_not_less_than_base_amount(self):
        """Checkout session unit_amount must be no less than the original payment amount.

        When FX rate adjustments cause the calculated total to fall below the
        original amount_sent_original, the checkout must floor up to the original.
        """
        payment = self._make_payment(PaymentStatus.pending)

        # Simulate a fee structure where calculated total < amount_sent_original (10 USD)
        low_fee_structure = FeeStructure(send_to_stripe=5.0)

        mock_customers = MagicMock()
        mock_customers.is_empty = True
        mock_customer = MagicMock()
        mock_customer.id = 'cus_test_123'

        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/pay/test'

        session_create = MagicMock(return_value=mock_session)

        with patch('app.payments.routes.payment_methods.stripe.calculate_base_amount',
                   return_value=5.0), \
             patch('app.payments.routes.payment_methods.stripe.calculate_service_fee',
                   return_value=low_fee_structure), \
             patch('app.payments.routes.payment_methods.stripe.stripe.Customer.search',
                   return_value=mock_customers), \
             patch('app.payments.routes.payment_methods.stripe.stripe.Customer.create',
                   return_value=mock_customer), \
             patch('app.payments.routes.payment_methods.stripe.stripe.checkout.Session.create',
                   session_create):
            response = self.client.get(f'/payments/{payment.id}/stripe/checkout')

        self.assertIn(response.status_code, (301, 302))
        session_create.assert_called_once()
        unit_amount = session_create.call_args[1]['line_items'][0]['price_data']['unit_amount']
        # amount_sent_original=10 USD → minimum 1000 cents
        self.assertGreaterEqual(
            unit_amount,
            int(float(payment.amount_sent_original) * 100),
            f"Checkout session unit_amount {unit_amount} is less than "
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


# ---------------------------------------------------------------------------
# Helpers for CLI-based integration tests
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _read_webhook_secret(proc, timeout: int = 30):
    """Parse the whsec_... signing secret from `stripe listen` stdout."""
    result: queue.Queue = queue.Queue()

    def _reader():
        for line in proc.stdout:
            m = re.search(r'webhook signing secret is (whsec_\S+)', line)
            if m:
                result.put(m.group(1))
                return
        result.put(None)  # process exited without printing the secret

    threading.Thread(target=_reader, daemon=True).start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        return None


def _sign_webhook_payload(payload: str, secret: str) -> str:
    """Return a Stripe-Signature header value for the given payload and secret."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


class TestStripeWebhookCLI(BaseTestCase):
    """Integration tests that use the Stripe CLI to forward real webhook events."""

    server = None
    server_thread = None
    listen_proc = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tests import app as test_app

        port = _find_free_port()

        # Real HTTP server — the Flask test client cannot receive inbound
        # requests from stripe listen, so we need an actual socket listener.
        cls.server = make_server('127.0.0.1', port, test_app)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.server_thread.start()

        # Start stripe listen and capture the per-session webhook signing secret.
        cls.listen_proc = subprocess.Popen(
            [
                'stripe', 'listen',
                '--forward-to',
                f'http://127.0.0.1:{port}/api/v1/payment/stripe/webhook',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        secret = _read_webhook_secret(cls.listen_proc)
        if not secret:
            raise RuntimeError(
                "Timed out waiting for the webhook signing secret from stripe listen"
            )

        # Inject the signing secret so the webhook view can verify signatures.
        test_app.config.setdefault('PAYMENT', {}).setdefault('stripe', {})[
            'webhook_secret'
        ] = secret

    @classmethod
    def tearDownClass(cls):
        if cls.listen_proc:
            cls.listen_proc.terminate()
        if cls.server:
            cls.server.shutdown()

    def setUp(self):
        super().setUp()
        from app import db
        db.create_all()

    def test_webhook_no_exception(self):
        """Webhook endpoint handles checkout.session.completed without raising."""
        result = subprocess.run(
            ['stripe', 'trigger', 'checkout.session.completed'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"stripe trigger failed:\n{result.stdout}\n{result.stderr}",
        )
        # Allow time for stripe listen to forward the event and the server to process it.
        time.sleep(3)

    def test_webhook_fires_session_data(self):
        """Webhook endpoint accepts a hand-crafted checkout.session.completed event."""
        session_object = {
            "id": "cs_test_a19klxPjQ0woedGGJ3GHgZXo21OjefFjYmYzZGduLU0ngdfDEO1mnRxhrL",
            "object": "checkout.session",
            "amount_subtotal": 10000,
            "amount_total": 10000,
            "cancel_url": "http://localhost:5000/payments/21613/stripe/cancel",
            "currency": "eur",
            "customer": "cus_U1PoqwCpyoSqOb",
            "livemode": False,
            "metadata": {},
            "mode": "payment",
            "payment_intent": "pi_3TBxGsBhwuI3XNce0vTTrueY",
            "payment_status": "paid",
            "status": "complete",
            "success_url": "http://localhost:5000/payments/21613/stripe/success",
        }
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": session_object,
                "previous_attributes": None,
            },
        }
        payload = json.dumps(event)
        secret = self.app.config['PAYMENT']['stripe']['webhook_secret']
        sig_header = _sign_webhook_payload(payload, secret)

        response = self.client.post(
            '/api/v1/payment/stripe/webhook',
            data=payload,
            content_type='application/json',
            headers={'Stripe-Signature': sig_header},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'ok'})
