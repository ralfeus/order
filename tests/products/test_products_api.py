from datetime import datetime

from tests import BaseTestCase, db
from app.models import Country
from app.currencies.models import Currency
from app.orders.models import Order, OrderProduct
from app.products.models import Product
from app.shipping.models import Shipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User


class TestProductsApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name="admin")
        self.user = User(
            username="user1_test_orders_api",
            email="root_test_orders_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
        )
        self.admin = User(
            username="root_test_orders_api",
            email="root_test_orders_api@name.com",
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
                Currency(code="RUR", rate=0.5),
                Country(id="c1", name="country1"),
                Product(id="0000", name="Test product", price=10, weight=10),
            ]
        )

    def test_get_products(self):
        res = self.try_user_operation(lambda: self.client.get("/api/v1/product"))
        self.assertEqual(
            res.json,
            [
                {
                    "available": True,
                    "synchronize": True,
                    "id": "0000",
                    "vendor_id": None,
                    "name": "Test product",
                    "name_english": None,
                    "name_russian": None,
                    "points": 0,
                    "price": 10,
                    "weight": 10,
                    "separate_shipping": False,
                    "purchase": True,
                    "color": None,
                    "image": "/static/images/no_image.jpg",
                }
            ],
        )
        res = self.client.get("/api/v1/product")
        self.assertGreater(len(res.json), 0)
        res = self.client.get("/api/v1/product/0000")
        self.assertEqual(len(res.json), 1)
        res = self.client.get("/api/v1/product/0")
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]["id"], "0000")
        res = self.client.get("/api/v1/product/999")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data, b"No product with code <999> was found")

    def test_search_product(self):
        self.try_add_entities(
            [
                Product(
                    id="0001",
                    name="Korean name 1",
                    name_english="English name",
                    name_russian="Russian name",
                    price=1,
                    available=True,
                )
            ]
        )
        res = self.try_user_operation(
            lambda: self.client.get("/api/v1/product/search/0001")
        )
        self.assertEqual(
            res.json,
            [
                {
                    "id": "0001",
                    "vendor_id": None,
                    "name": "Korean name 1",
                    "name_english": "English name",
                    "name_russian": "Russian name",
                    "points": 0,
                    "price": 1,
                    "weight": 0,
                    "separate_shipping": False,
                    "available": True,
                    "synchronize": True,
                    "purchase": True,
                    "color": None,
                    "image": "/static/images/no_image.jpg",
                }
            ],
        )

    def test_create_product(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        res = self.try_admin_operation(
            lambda: self.client.post(
                f"/api/v1/admin/product/{gen_id}",
                json={"id": gen_id, "name": "Test product"},
            )
        )
        self.assertEqual(res.status_code, 200)
        product = Product.query.get(gen_id)
        self.assertIsNotNone(product)

    def test_edit_product(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities(
            [
                Product(
                    id="0001",
                    name="Korean name 1",
                    name_english="English name",
                    name_russian="Russian name",
                    price=1,
                    available=True,
                    image_id=1111,
                )
            ]
        )
        res = self.try_admin_operation(
            lambda: self.client.post(
                f"/api/v1/admin/product/{gen_id}",
                json={"id": gen_id, "name": "Test product"},
            )
        )
        self.assertEqual(res.status_code, 200)
        product = Product.query.get(gen_id)
        self.assertIsNotNone(product)
        self.assertEqual(product.name, "Test product")

    def test_delete_product(self):
        gen_id = f"{__name__}-{int(datetime.now().timestamp())}"
        self.try_add_entities([
            Product(
                id=gen_id,
                name="Korean name 1",
                name_english="English name",
                name_russian="Russian name",
                price=1,
                available=True,
                image_id=1111
            )
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f"/api/v1/admin/product/{gen_id}")
        )
