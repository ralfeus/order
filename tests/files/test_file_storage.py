"""
Tests for the centralised file-storage layout.

Expected structure (DATA_PATH = "tests/data" in test config):
  DATA_PATH/upload/   – user-uploaded files (payment evidences, Stripe receipts, …)
  DATA_PATH/products/ – product images fetched during import
  DATA_PATH/po/       – PO-creation screenshots

Two groups of tests:
  1. File-creation – verify that helper functions resolve to the right subfolder.
  2. API-reading   – verify that /upload/<path> and /products/<path> serve files
                     from the correct physical directories.
"""
import os

from flask import current_app

from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User

# Password hash for "1" (shared with other test suites)
_PASSWORD_HASH = (
    "pbkdf2:sha256:150000$bwYY0rIO"
    "$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576"
)


class TestFileStorage(BaseTestCase):
    """Verify that the three data sub-folders work as expected."""

    # ── fixtures ────────────────────────────────────────────────────────

    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name="admin")
        self.user = User(
            username="user_test_file_storage",
            email="user_test_file_storage@test.com",
            password_hash=_PASSWORD_HASH,
            enabled=True,
        )
        self.admin = User(
            username="admin_test_file_storage",
            email="admin_test_file_storage@test.com",
            password_hash=_PASSWORD_HASH,
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities([self.user, self.admin, admin_role])
        self._test_files: list[str] = []

    def tearDown(self):
        for path in self._test_files:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        super().tearDown()

    # ── helpers ─────────────────────────────────────────────────────────

    def _abs_data_path(self, *parts: str) -> str:
        """Resolve DATA_PATH from config to an absolute path, then join *parts."""
        base = current_app.config.get("DATA_PATH", "/app/data")
        if not os.path.isabs(base):
            base = os.path.join(os.getcwd(), base)
        return os.path.join(base, *parts)

    # ── 1. File-creation tests ───────────────────────────────────────────

    def test_write_to_upload_folder(self):
        """File written through get_upload_path() lands in DATA_PATH/upload/."""
        from app.tools import get_upload_path, write_to_file

        target = os.path.join(get_upload_path(), "test_write_upload.bin")
        self._test_files.append(target)

        write_to_file(target, b"upload content")

        self.assertTrue(os.path.exists(target))
        self.assertTrue(target.startswith(self._abs_data_path("upload")))

    def test_write_to_products_folder(self):
        """File written through get_products_path() lands in DATA_PATH/products/."""
        from app.tools import get_products_path, write_to_file

        target = os.path.join(get_products_path(), "test_write_product.jpg")
        self._test_files.append(target)

        write_to_file(target, b"product image bytes")

        self.assertTrue(os.path.exists(target))
        self.assertTrue(target.startswith(self._abs_data_path("products")))

    def test_write_to_po_folder(self):
        """File written through get_po_path() lands in DATA_PATH/po/."""
        from app.tools import get_po_path, write_to_file

        target = os.path.join(get_po_path(), "test_write_po.png")
        self._test_files.append(target)

        write_to_file(target, b"screenshot bytes")

        self.assertTrue(os.path.exists(target))
        self.assertTrue(target.startswith(self._abs_data_path("po")))

    # ── 2. API-reading tests ─────────────────────────────────────────────

    def test_api_read_from_upload(self):
        """GET /upload/<path> serves a file stored in DATA_PATH/upload/."""
        upload_dir = self._abs_data_path("upload")
        os.makedirs(upload_dir, exist_ok=True)

        target = os.path.join(upload_dir, "api_test_evidence.jpg")
        expected = b"fake payment evidence"
        with open(target, "wb") as f:
            f.write(expected)
        self._test_files.append(target)

        res = self.try_user_operation(
            lambda: self.client.get("/upload/api_test_evidence.jpg")
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, expected)

    def test_api_read_from_products(self):
        """GET /products/<path> serves a file stored in DATA_PATH/products/."""
        products_dir = self._abs_data_path("products")
        os.makedirs(products_dir, exist_ok=True)

        target = os.path.join(products_dir, "api_test_product.jpg")
        expected = b"fake product image data"
        with open(target, "wb") as f:
            f.write(expected)
        self._test_files.append(target)

        res = self.try_user_operation(
            lambda: self.client.get("/products/api_test_product.jpg")
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, expected)
