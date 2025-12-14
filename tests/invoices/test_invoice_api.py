from datetime import datetime

from app.models import Country
from app.currencies.models import Currency
from app.invoices.models import Invoice, InvoiceItem
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.users.models.role import Role
from app.users.models.user import User
from tests import BaseTestCase, db


class TestInvoiceClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(id=10, name="admin")
        self.admin = User(
            username="root_test_invoice_api",
            email="root_test_invoice_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
            roles=[admin_role],
        )
        self.user = User(
            id=10,
            username="user1_test_invoice_api",
            email="user_test_invoice_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
        )
        self.try_add_entities(
            [
                self.admin,
                self.user,
                admin_role,
                Country(id="c1", name="country1"),
                Currency(code="USD", rate=0.5, enabled=True),
                Product(
                    id="SHIPPING",
                    name="Shipping",
                    weight=0,
                    available=False,
                    synchronize=False,
                    separate_shipping=False,
                    purchase=False,
                ),
            ]
        )

    def try_admin_operation(self, operation):
        """
        Superseeds base method to add class-specific user and admin credentials
        """
        return super().try_admin_operation(
            operation, "user1_test_invoice_api", "1", "root_test_invoice_api", "1"
        )

    def test_create_invoice(self):
        """Test creation of invoice"""
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        id_prefix = datetime.now().strftime("INV-%Y-%m-")
        self.try_add_entities([Product(id=gen_id, name="Product 1", price=1)])
        order = Order(id=gen_id, user=self.user)
        suborder = Suborder(order=order)
        self.try_add_entities(
            [
                order,
                suborder,
                OrderProduct(suborder=suborder, product_id=gen_id, quantity=1, price=1),
            ]
        )
        res = self.try_user_operation(
            lambda: self.client.post(
                "/api/v1/invoice/new",
                json={"order_ids": [gen_id], "currency": "USD", "rate": 0.5},
            )
        )
        self.assertEqual(res.json["invoice_id"], f"{id_prefix}0001") # type: ignore
        invoice = Invoice.query.get(res.json["invoice_id"]) # type: ignore
        self.assertEqual(len(invoice.orders), 1)
        self.assertEqual(invoice.invoice_items_count, 2)

    def test_save_invoice(self):
        """Tests update of invoice"""
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Invoice(
                    id=gen_id,
                    customer="Customer 1",
                    currency_code="USD",
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime.now(),
                )
            ]
        )
        res = self.try_admin_operation(
            lambda: self.client.post(
                f"/api/v1/admin/invoice/{gen_id}", json={"customer": "Customer 2"}
            )
        )
        self.assertEqual(res.status_code, 200)
        invoice = Invoice.query.get(gen_id)
        self.assertEqual(invoice.customer, "Customer 2")

    def test_get_invoices(self):
        """Test getting invoices"""
        self.try_add_entities(
            [
                Product(id="0001", name="Product 1", name_english="P1", weight=10),
                Invoice(
                    id="INV-2020-00-00",
                    country_id="c1",
                    customer="Customer 1",
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0),
                    currency_code="USD",
                ),
                InvoiceItem(
                    invoice_id="INV-2020-00-00", product_id="0001", price=10, quantity=1
                ),
                Order(
                    id=__name__ + "-1",
                    invoice_id="INV-2020-00-00",
                    country_id="c1",
                    customer_name="Customer 1",
                    user=self.user,
                ),
            ]
        )
        self.try_user_operation(lambda: self.client.get("/api/v1/invoice"))
        res = self.client.get("/api/v1/invoice/INV-2020-00-00")
        self.assertEqual(len(res.json), 1)  # type: ignore
        assert res.json[0] == ( #type: ignore
            {  # type: ignore
                "address": None,
                "country": "country1",
                "customer": "Customer 1",
                "payee": None,
                "id": "INV-2020-00-00",
                "export_id": None,
                "invoice_items": [
                    {
                        "id": 1,
                        "invoice_id": "INV-2020-00-00",
                        "product_id": "0001",
                        "product": "P1",
                        "price": 10.0,
                        "weight": 10,
                        "quantity": 1,
                        "subtotal": 10.0,
                        "when_created": None,
                        "when_changed": None,
                    }
                ],
                "orders": [__name__ + "-1"],
                "shippings": [],
                "phone": None,
                "currency_code": "USD",
                "total": 10.0,
                "weight": 10,
                "when_changed": "2020-01-01 01:00:00",
                "when_created": "2020-01-01 01:00:00",
            })

    def test_get_old_invoice(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Product(id=gen_id, name="Product 1", weight=10),
                Invoice(
                    id=gen_id,
                    country_id="c1",
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0),
                    currency_code="USD",
                ),
                Order(id=gen_id, invoice_id=gen_id, country_id="c1", user=self.user),
            ]
        )
        suborder = Suborder(order_id=gen_id)
        self.try_add_entities(
            [
                suborder,
                OrderProduct(
                    suborder=suborder, product_id=gen_id, price=10, quantity=1
                ),
            ]
        )
        res = self.try_user_operation(
            lambda: self.client.get(f"/api/v1/invoice/{gen_id}")
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1) # type: ignore
        self.assertEqual(
            res.json[0], # type: ignore
            {
                "address": None,
                "country": "country1",
                "customer": None,
                "payee": None,
                "id": gen_id,
                "export_id": None,
                "invoice_items": [
                    {
                        "id": 1,
                        "invoice_id": gen_id,
                        "product_id": gen_id,
                        "product": "Product 1",
                        "price": 5.0,
                        "weight": 10,
                        "quantity": 1,
                        "subtotal": 5.0,
                        "when_created": None,
                        "when_changed": None,
                    }
                ],
                "orders": [gen_id],
                "shippings": [],
                "phone": None,
                "currency_code": "USD",
                "total": 5.0,
                "weight": 10,
                "when_changed": "2020-01-01 01:00:00",
                "when_created": "2020-01-01 01:00:00",
            },
        )

    def test_get_invoice_excel(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Product(id=gen_id, weight=1),
                Invoice(id=gen_id, country_id="c1", currency_code="USD"),
                Order(id=gen_id, invoice_id=gen_id, country_id="c1", user=self.user),
                InvoiceItem(invoice_id=gen_id, product_id=gen_id, price=1, quantity=1),
            ]
        )
        self.try_user_operation(
            lambda: self.client.get(f"/api/v1/invoice/{gen_id}/excel")
        )
        self.client.get(
            f"/api/v1/invoice/{gen_id}/excel?template=[local]/tenant_specific.xlsx"
        )
        self.assertRaises(
            FileNotFoundError,
            lambda: self.client.get(
                f"/api/v1/invoice/{gen_id}/excel?template=[local]/tenant_specific1.xlsx"
            ),
        )

    def test_get_invoice_cumulative_excel(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Product(id=gen_id, weight=1),
                Invoice(id=gen_id, country_id="c1", currency_code="USD"),
                Order(id=gen_id, invoice_id=gen_id, country_id="c1", user=self.user),
                InvoiceItem(invoice_id=gen_id, product_id=gen_id, price=1, quantity=1),
            ]
        )
        res = self.try_user_operation(
            lambda: self.client.get(
                f"/api/v1/invoice/excel?invoices={gen_id}&invoices={gen_id}"
            )
        )
        self.assertTrue(res.status_code, 200)

    def test_create_invoice_item(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        order = Order(id=gen_id, user=self.admin)
        self.try_add_entities([Product(id=gen_id, name="Product 1")])
        self.try_add_entities(
            [
                order,
                Suborder(id=gen_id, order=order),
                OrderProduct(
                    suborder_id=gen_id, product_id=gen_id, price=10, quantity=10
                ),
                Invoice(id=gen_id, order_id=gen_id, currency_code="USD"),
            ]
        )
        self.try_admin_operation(
            lambda: self.client.post(f"/api/v1/admin/invoice/{gen_id}/item/new")
        )
        res = self.client.post(
            f"/api/v1/admin/invoice/{gen_id}/item/new",
            json={
                "invoice_id": gen_id,
                "product_id": gen_id,
                "price": 10,
                "quantity": 10,
            },
        )
        self.assertTrue(res.status_code, 200)

    def test_save_invoice_item(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        order = Order(id=gen_id, user=self.admin)
        self.try_add_entities([Product(id=gen_id, name="Product 1")])
        self.try_add_entities(
            [
                order,
                Suborder(id=gen_id, order=order),
                OrderProduct(
                    suborder_id=gen_id, product_id=gen_id, price=10, quantity=10
                ),
                Invoice(id=gen_id, order_id=gen_id, currency_code="USD"),
                InvoiceItem(
                    id=10, invoice_id=gen_id, product_id=gen_id, price=10, quantity=10
                ),
            ]
        )
        self.try_admin_operation(
            lambda: self.client.post(f"/api/v1/admin/invoice/{gen_id}/item/10")
        )
        res = self.client.post(
            f"/api/v1/admin/invoice/{gen_id}/item/10", json={"price": 20}
        )
        self.assertEqual(res.status_code, 200)
        invoice_item = InvoiceItem.query.get(10)
        self.assertEqual(invoice_item.price, 20)

    def test_delete_invoice_item(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        order = Order(id=gen_id, user=self.admin)
        self.try_add_entities([Product(id=gen_id, name="Product 1")])
        self.try_add_entities(
            [
                order,
                Suborder(id=gen_id, order=order),
                OrderProduct(
                    suborder_id=gen_id, product_id=gen_id, price=10, quantity=10
                ),
                Invoice(id=gen_id, order_id=gen_id, currency_code="USD"),
                InvoiceItem(
                    id=10, invoice_id=gen_id, product_id=gen_id, price=10, quantity=10
                ),
            ]
        )
        res = self.try_admin_operation(
            lambda: self.client.delete(f"/api/v1/admin/invoice/{gen_id}/item/10")
        )
        self.assertEqual(res.status_code, 200)
        invoice_item = InvoiceItem.query.get(10)
        self.assertEqual(invoice_item, None)

    def test_get_invoice_templates(self):
        res = self.try_user_operation(
            lambda: self.client.get("/api/v1/invoice/template")
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 2) # type: ignore
        self.assertEqual(res.json[1], "[local]/tenant_specific.xlsx") # type: ignore

    def test_create_invoice_with_non_owned_order(self):
        """Test creation of invoice with non-owned order should fail"""
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities([Product(id=gen_id, name="Product 1", price=1)])
        order = Order(id=gen_id, user=self.admin)
        suborder = Suborder(order=order)
        self.try_add_entities(
            [
                order,
                suborder,
                OrderProduct(suborder=suborder, product_id=gen_id, quantity=1, price=1),
            ]
        )
        res = self.try_user_operation(
            lambda: self.client.post(
                "/api/v1/invoice/new",
                json={"order_ids": [gen_id], "currency": "USD", "rate": 0.5},
            )
        )
        # Should fail because order is not owned by user
        self.assertEqual(res.status_code, 409)

    def test_get_invoices_as_user(self):
        """Test getting invoices as user"""
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Product(id="0001", name="Product 1", name_english="P1", weight=10),
                Invoice(
                    id=gen_id,
                    country_id="c1",
                    customer="Customer 1",
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0),
                    currency_code="USD",
                ),
                InvoiceItem(
                    invoice_id=gen_id, product_id="0001", price=10, quantity=1
                ),
                Order(
                    id=gen_id,
                    invoice_id=gen_id,
                    country_id="c1",
                    customer_name="Customer 1",
                    user=self.user,
                ),
            ]
        )
        res = self.try_user_operation(lambda: self.client.get("/api/v1/invoice"))
        self.assertEqual(len(res.json), 1)  # type: ignore
        assert res.json[0]["id"] == gen_id #type: ignore

    def test_get_invoices_as_user_non_owned(self):
        """Test getting invoices as user for non-owned invoice"""
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Product(id="0001", name="Product 1", name_english="P1", weight=10),
                Invoice(
                    id=gen_id,
                    country_id="c1",
                    customer="Customer 1",
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0),
                    currency_code="USD",
                ),
                InvoiceItem(
                    invoice_id=gen_id, product_id="0001", price=10, quantity=1
                ),
                Order(
                    id=gen_id,
                    invoice_id=gen_id,
                    country_id="c1",
                    customer_name="Customer 1",
                    user=self.admin,
                ),
            ]
        )
        res = self.try_user_operation(lambda: self.client.get("/api/v1/invoice"))
        assert len(res.json) == 0 #type: ignore
