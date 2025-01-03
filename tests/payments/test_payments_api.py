"""
Tests of sale order functionality API
"""

from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.payments.models.payment import Payment, PaymentStatus
from app.payments.models.payment_method import PaymentMethod
from app.users.models.role import Role
from app.users.models.user import User


class TestPaymentsApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name="admin")
        self.user = User(
            username="user1_test_payments_api",
            email="root_test_payments_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
        )
        self.admin = User(
            username="root_test_payments_api",
            email="root_test_payments_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities(
            [
                self.user,
                self.admin,
                admin_role,
                Currency(code="USD", rate=0.5),
                Currency(code="EUR", rate=0.5),
                PaymentMethod(id=1),
            ]
        )

    def test_create_payment(self):
        res = self.try_user_operation(
            lambda: self.client.post(
                "/api/v1/payment",
                json={
                    "sender_name": "test",
                    "user_id": self.user.id,
                    "currency_code": "USD",
                    "amount_sent_original": 100,
                    "payment_method": {"id": 1},
                },
            )
        )
        self.assertIsNone(res.json.get("error")) # type: ignore
        res = self.client.post(
            "/api/v1/payment",
            json={
                "sender_name": "test",
                "user_id": self.user.id,
                "currency_code": "USD",
                "amount_sent_original": "100.50",
                "payment_method": {"id": 1},
            },
        )
        self.assertIsNone(res.json.get("error")) # type: ignore
        res = self.client.post(
            "/api/v1/payment",
            json={
                "sender_name": "test",
                "user_id": self.user.id,
                "currency_code": "USD",
                "amount_sent_original": "100,50",
                "payment_method": {"id": 1},
            },
        )
        self.assertIsNone(res.json.get("error")) # type: ignore
        res = self.client.post(
            "/api/v1/payment",
            json={
                "sender_name": "test",
                "user_id": self.user.id,
                "currency_code": "USD",
                "amount_sent_original": "100.50.3",
                "payment_method": {"id": 1},
            },
        )
        self.assertIsNotNone(res.json.get("error")) # type: ignore
        res = self.client.post(
            "/api/v1/payment",
            json={
                "sender_name": "test",
                "user_id": self.user.id,
                "currency_code": "CZK",
                "amount_sent_original": 100,
                "payment_method": {"id": 1},
            },
        )
        self.assertIsNotNone(res.json.get("error")) # type: ignore

    def test_reject_after_approved(self):
        currency = Currency.query.get('USD')
        payment = Payment(
            user_id=self.user.id,
            amount_sent_original=10,
            currency=currency,
            amount_received_krw=10,
            status=PaymentStatus.approved,
        )
        self.try_add_entities([payment])
        res = self.try_admin_operation(
            lambda: self.client.post(
                f"/api/v1/admin/payment/{payment.id}", json={"status": "rejected"}
            )
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.user.balance, -10)
