"""
Tests of sale order functionality API
"""

from datetime import datetime
from io import BytesIO

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
        self.other_user = User(
            username="other_user_test_payments_api",
            email="other_test_payments_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
        )
        usd_currency = Currency(code="USD", rate=0.5)
        eur_currency = Currency(code="EUR", rate=0.5)
        payment_method = PaymentMethod(id=1)
        self.try_add_entities(
            [
                self.user,
                self.admin,
                self.other_user,
                admin_role,
                usd_currency,
                eur_currency,
                payment_method,
            ]
        )

        # Create test payments
        self.payment1 = Payment(
            user=self.user,
            sender_name="Test Sender 1",
            currency=usd_currency,
            amount_sent_original=100.0,
            amount_sent_krw=200.0,
            payment_method_id=1,
            status=PaymentStatus.pending,
            when_created=datetime.now(),
        )
        self.payment2 = Payment(
            user=self.user,
            sender_name="Test Sender 2",
            currency=eur_currency,
            amount_sent_original=50.0,
            amount_sent_krw=100.0,
            payment_method_id=1,
            status=PaymentStatus.approved,
            when_created=datetime.now(),
        )
        self.payment3 = Payment(
            user=self.other_user,
            sender_name="Test Sender 3",
            currency=usd_currency,
            amount_sent_original=75.0,
            amount_sent_krw=150.0,
            payment_method_id=1,
            status=PaymentStatus.pending,
            when_created=datetime.now(),
        )
        self.try_add_entities([self.payment1, self.payment2, self.payment3])



    def test_create_payment(self):
        res = self.try_user_operation(
            lambda: self.client.post(
                "/api/v1/payment",
                json={
                    "sender_name": "test",
                    "user_id": self.user.id, #type:ignore
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
                "user_id": self.user.id, #type:ignore
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
                "user_id": self.user.id, #type:ignore
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
                "user_id": self.user.id, #type:ignore
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
                "user_id": self.user.id, #type:ignore
                "currency_code": "CZK",
                "amount_sent_original": 100,
                "payment_method": {"id": 1},
            },
        )
        self.assertIsNotNone(res.json.get("error")) # type: ignore

    def test_reject_after_approved(self):
        currency = Currency.query.get('USD')
        payment = Payment(
            user_id=self.user.id, #type:ignore
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
        self.assertEqual(self.user.balance, -10) #type:ignore

    def test_user_get_payments(self):
        # Test regular user gets only their payments
        res = self.try_user_operation(
            lambda: self.client.get("/api/v1/payment")
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or []
        self.assertEqual(len(data), 2)  # user has 2 payments
        payment_ids = [p['id'] for p in data]
        self.assertIn(self.payment1.id, payment_ids)
        self.assertIn(self.payment2.id, payment_ids)
        self.assertNotIn(self.payment3.id, payment_ids)

        # Test admin gets all payments
        self.logout()
        res = self.try_admin_operation(
            lambda: self.client.get("/api/v1/payment"),
            admin_only=True
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)  # admin sees all 3 payments
        payment_ids = [p['id'] for p in data]
        self.assertIn(self.payment1.id, payment_ids)
        self.assertIn(self.payment2.id, payment_ids)
        self.assertIn(self.payment3.id, payment_ids)

        # Test get specific payment by ID (user's own payment)
        self.logout()
        res = self.try_user_operation(
            lambda: self.client.get(f"/api/v1/payment/{self.payment1.id}")
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or []
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.payment1.id)

        # Test get specific payment by ID (admin accessing any payment)
        self.logout()
        res = self.try_admin_operation(
            lambda: self.client.get(f"/api/v1/payment/{self.payment3.id}"),
            admin_only=True
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.payment3.id)

        # Test filter by status
        self.logout()
        res = self.try_user_operation(
            lambda: self.client.get("/api/v1/payment?status=pending")
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or []
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.payment1.id)

        # Test 404 when no payments found
        res = self.client.get("/api/v1/payment?status=cancelled")
        self.assertEqual(res.status_code, 404)

        # Test unauthorized access (no login)
        self.logout()
        res = self.client.get("/api/v1/payment")
        self.assertEqual(res.status_code, 302)  # Redirect to login

    def test_admin_get_payments(self):
        # Test regular user gets only their payments
        res = self.try_user_operation(
            lambda: self.client.get("/api/v1/admin/payment")
        )
        self.assertEqual(res.status_code, 302)

        # Test admin gets all payments
        self.logout()
        res = self.try_admin_operation(
            lambda: self.client.get("/api/v1/admin/payment")
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)  # admin sees all 3 payments
        payment_ids = [p['id'] for p in data]
        self.assertIn(self.payment1.id, payment_ids)
        self.assertIn(self.payment2.id, payment_ids)
        self.assertIn(self.payment3.id, payment_ids)

        res = self.client.get(f"/api/v1/admin/payment/{self.payment3.id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or []
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.payment3.id)

        # Test 404 when no payments found
        res = self.client.get("/api/v1/admin/payment?status=cancelled")
        self.assertEqual(res.status_code, 404)

        # Test unauthorized access (no login)
        self.logout()
        res = self.client.get("/api/v1/admin/payment")
        self.assertEqual(res.status_code, 302)  # Redirect to login

    def test_user_upload_payment_evidence(self):
        # Test no files uploaded to /evidence
        res = self.try_user_operation(
            lambda: self.client.post("/api/v1/payment/evidence", data={})
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or {}
        self.assertEqual(data.get('upload', {}).get('id'), [])
        self.assertEqual(data.get('files', {}).get('files'), {})

        # Test one file uploaded to /evidence
        file_data = BytesIO(b'test file content')
        file_data.seek(0)
        res = self.client.post(
            "/api/v1/payment/evidence",
            data={'file': (file_data, 'test.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or {}
        self.assertEqual(len(data.get('upload', {}).get('id', [])), 1)
        upload_id = data.get('upload', {}).get('id', [])[0]
        self.assertIn(upload_id, data.get('files', {}).get('files', {}))

        # Test two files uploaded to /evidence
        file_data1 = BytesIO(b'content1')
        file_data2 = BytesIO(b'content2')
        res = self.client.post(
            "/api/v1/payment/evidence",
            data={
                'file1': (file_data1, 'test1.jpg'),
                'file2': (file_data2, 'test2.jpg')
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json() or {}
        self.assertEqual(len(data.get('upload', {}).get('id', [])), 2)
        self.assertEqual(len(data.get('files', {}).get('files', {})), 2)

        # Test one file uploaded to payment user doesn't own
        file_data = BytesIO(b'unauthorized content')
        res = self.client.post(
            f"/api/v1/payment/{self.payment3.id}/evidence",
            data={'file': (file_data, 'test.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(res.status_code, 403)

        # Test one file uploaded to approved payment
        res = self.client.post(
            f"/api/v1/payment/{self.payment2.id}/evidence",
            data={'file': (BytesIO(b'content'), 'test.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(res.status_code, 409)

        # Test no file uploaded when payment_id provided
        res = self.client.post(
            f"/api/v1/payment/{self.payment1.id}/evidence",
            data={},
            content_type='multipart/form-data'
        )
        self.assertEqual(res.status_code, 400)

        # Logout after user operations
        self.logout()

        # Test one file uploaded by admin to payment they don't own
        res = self.try_admin_operation(
            lambda: self.client.post(
                f"/api/v1/payment/{self.payment3.id}/evidence",
                data={'file': (BytesIO(b'admin content'), 'test.jpg')},
                content_type='multipart/form-data'
            ),
            admin_only=True
        )
        self.assertEqual(res.status_code, 200)
        # Verify the file was attached
        payment = Payment.query.get(self.payment3.id)
        self.assertGreater(payment.evidences.count(), 0)
