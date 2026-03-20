import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lxml.etree import fromstring
from tests import BaseTestCase
from flask import current_app

from app import db
from app.addresses.models import Address
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
import app.products.models as pr
import app.purchase.models as p
from app.purchase.models.vendors.atomy_quick import (
    AtomyQuick,
    MESSAGE_REGISTRATION_NEEDED,
)
from app.users.models import Role, User
from common.exceptions import AtomyLoginError, ProductNotAvailableError, PurchaseOrderError


# ---------------------------------------------------------------------------
# Mock helpers for HTTP / HTML responses used by multiple tests
# ---------------------------------------------------------------------------

def invoke_curl(url, **kwargs) -> tuple[str, str]:
    url_parts = {
        '/goods/goodsResult': f'''
            <html>
                <input id="goodsInfo_0" data-goodsinfo="{{\\"goodsNo\\": \\"000000\\"}}" />
                {'<button option-role="" />' if '000002' in (kwargs.get('raw_data') or '') else ''}
            </html>''',
        '/order/finish': 'saleNum: 000, ipgumAccountNo: 456, ipgumAmt: 000',
        # CSS selector used is "div.my_odr_gds>ul>li" – <ul> must be present
        '/mypage/orderList': '''
            <div class="my_odr_gds">
                <ul>
                <li>
                    <input type="hidden" name="hSaleNum" value="7012504030031927"/>
                    <span class="m-stat">Shipping</span>
                </li>
                </ul>
            </div>''',
    }

    for url_part, response in url_parts.items():
        if url_part in url:
            return response, "HTTP/2 200 OK"
    return "", "HTTP/2 200 OK"


def get_html(url, **kwargs):
    return fromstring(invoke_curl(url, **kwargs)[0])


# ---------------------------------------------------------------------------
# Playwright mock – used by TestPurchaseOrdersVendorAtomyQuick
# ---------------------------------------------------------------------------

def _build_playwright_mock():
    """Build a sync_playwright mock where every locator().count() returns 0
    and locator().page refers back to the page so remove_popup() works."""
    page = MagicMock()

    locator = MagicMock()
    locator.count.return_value = 0
    locator.is_disabled.return_value = False
    locator.page = page           # KEY: lets remove_popup() do object.page.locator().count()

    page.locator.return_value = locator
    page.evaluate.return_value = True  # __is_product_allowed always returns True

    wff = MagicMock()
    wff.json_value.return_value = 'form_gone'   # login succeeds, no alert
    page.wait_for_function.return_value = wff

    browser = MagicMock()
    browser.new_context.return_value.new_page.return_value = page

    ctx = MagicMock()
    ctx.chromium.launch.return_value = browser
    ctx.chromium.connect.return_value = browser

    pw = MagicMock()
    pw.return_value.__enter__.return_value = ctx
    pw.return_value.__exit__.return_value = False
    return pw


_PW_MOCK = _build_playwright_mock()

# Reusable product mock: returns a quantity-input locator + product info dict
_PRODUCT_OK_MOCK = MagicMock(
    return_value=(MagicMock(), {"goodsNo": "000000", "isIndividualDelivery": "0"})
)


# ---------------------------------------------------------------------------
# Main purchase-order tests
# ---------------------------------------------------------------------------

@patch("app.purchase.models.vendors.atomy_quick.sync_playwright", _PW_MOCK)
@patch("app.purchase.models.vendors.atomy_quick.expect", MagicMock())
@patch("app.purchase.models.vendors.atomy_quick.sleep", MagicMock())
class TestPurchaseOrdersVendorAtomyQuick(BaseTestCase):

    def setUp(self):
        super().setUp()
        db.create_all()

        admin_role = Role(name="admin")
        self.user = User(
            username="user1_test_po_api",
            email="root_test_po_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
        )
        self.admin = User(
            username="root_test_po_api",
            email="root_test_po_api@name.com",
            password_hash="pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576",
            enabled=True,
            roles=[admin_role],
        )
        self.try_add_entities([
            self.user, self.admin, admin_role,
            pr.Product(id="000000", name="Test product", price=10, weight=10),
            pr.Product(id="000002", name="Unavailable option", price=10, weight=10),
        ])

        # Patch every private method that touches the real browser so tests
        # exercise orchestration logic only; __get_product_by_id is patched
        # per-test to allow differentiated product behaviour.
        self._browser_patches = [
            patch.object(AtomyQuick, '_AtomyQuick__login'),
            patch.object(AtomyQuick, '_AtomyQuick__init_quick_order'),
            patch.object(AtomyQuick, '_AtomyQuick__set_purchase_date'),
            patch.object(AtomyQuick, '_AtomyQuick__register_cart', return_value={}),
            patch.object(AtomyQuick, '_AtomyQuick__set_receiver_mobile'),
            patch.object(AtomyQuick, '_AtomyQuick__set_receiver_name'),
            patch.object(AtomyQuick, '_AtomyQuick__set_receiver_address'),
            patch.object(AtomyQuick, '_AtomyQuick__set_local_shipment'),
            patch.object(AtomyQuick, '_AtomyQuick__set_payment_params'),
            patch.object(AtomyQuick, '_AtomyQuick__set_tax_info'),
            patch.object(AtomyQuick, '_AtomyQuick__submit_order',
                         return_value=('000', '456', '000')),
        ]
        for bp in self._browser_patches:
            bp.start()

    def tearDown(self):
        for bp in self._browser_patches:
            bp.stop()
        return super().tearDown()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_po(self, product_id="000000"):
        subcustomer = Subcustomer(username="s1", password="p1")
        order = Order()
        so = Suborder(order)
        op = OrderProduct(suborder=so, product_id=product_id, quantity=10)
        company = p.Company(bank_id="32")
        po = p.PurchaseOrder(
            so,
            customer=subcustomer,
            company=company,
            contact_phone="010-1234-1234",
            payment_phone="010-1234-1234",
            address=Address(address_1="", address_2=""),
        )
        self.try_add_entities([order, so, op, po, company])
        return p.PurchaseOrder.query.get(po.id)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    @patch.object(AtomyQuick, '_AtomyQuick__get_product_by_id', new=_PRODUCT_OK_MOCK)
    def test_post_purchase_order(self):
        po = self._make_po("000000")
        res = AtomyQuick(config=current_app.config).post_purchase_order(po)
        self.assertEqual(res[0].payment_account, "456")

    @patch.object(AtomyQuick, '_AtomyQuick__get_product_by_id',
                  new=MagicMock(side_effect=ProductNotAvailableError("000000", "Out of stock")))
    def test_post_purchase_order_unavailable_product(self):
        po = self._make_po("000000")
        with self.assertRaises(PurchaseOrderError):
            AtomyQuick(config=current_app.config).post_purchase_order(po)

    @patch.object(AtomyQuick, '_AtomyQuick__get_product_by_id', new=_PRODUCT_OK_MOCK)
    def test_post_purchase_order_exempted_product(self):
        self.try_add_entities([
            pr.Product(id="000001", name="Test product 1", price=10, weight=10, purchase=False),
        ])
        subcustomer = Subcustomer(username="s1", password="p1")
        order = Order()
        so = Suborder(order)
        op = OrderProduct(suborder=so, product_id="000000", quantity=10)
        op1 = OrderProduct(suborder=so, product_id="000001", quantity=10)
        company = p.Company(bank_id="32")
        po = p.PurchaseOrder(
            so,
            customer=subcustomer,
            company=company,
            contact_phone="010-1234-1234",
            payment_phone="010-1234-1234",
            address=Address(address_1="", address_2=""),
        )
        self.try_add_entities([order, so, op, op1, po, company])
        po = p.PurchaseOrder.query.get(po.id)
        # Must complete without error; the purchase=False product is skipped
        AtomyQuick(config=current_app.config).post_purchase_order(po)

    @patch.object(AtomyQuick, '_AtomyQuick__get_product_by_id',
                  new=MagicMock(side_effect=ProductNotAvailableError("000002", "option unavailable")))
    def test_post_purchase_order_unavailable_option(self):
        po = self._make_po("000002")
        with self.assertRaises(PurchaseOrderError):
            AtomyQuick(config=current_app.config).post_purchase_order(po)

    @patch("app.purchase.models.vendors.atomy_quick.atomy_login2",
           return_value="fake_cookie=value")
    @patch("app.purchase.models.vendors.atomy_quick.get_html", side_effect=get_html)
    def test_get_po_status(self, mock_get_html, mock_atomy_login):
        subcustomer = Subcustomer(username="40697460", password="Magnit135!")
        suborder = Suborder(order=Order())
        po = p.PurchaseOrder(
            suborder=suborder, vendor_po_id='7012504030031927', customer=subcustomer
        )
        self.try_add_entities([subcustomer, suborder, po])
        AtomyQuick(config=current_app.config).update_purchase_order_status(po)


# ---------------------------------------------------------------------------
# Unit tests for __login (no real browser)
# ---------------------------------------------------------------------------

class TestAtomyQuickLoginUnit(BaseTestCase):
    """Unit tests for __login — no real browser required."""

    def _make_page_mock(self, has_popup: bool):
        page = MagicMock()
        close_btn_locator = MagicMock()
        close_btn_locator.count.return_value = 1 if has_popup else 0
        form_locator = MagicMock()

        def locator_side_effect(selector):
            if 'close-button' in selector:
                return close_btn_locator
            return form_locator

        page.locator.side_effect = locator_side_effect
        wff_result = MagicMock()
        wff_result.json_value.return_value = 'form_gone'
        page.wait_for_function.return_value = wff_result
        return page, close_btn_locator

    def test_login_dismisses_popup_when_present(self):
        """Regression: popup close-button must be clicked before the login
        button; without this the click is intercepted and wait_for_function
        times out."""
        page, close_btn = self._make_page_mock(has_popup=True)
        po = SimpleNamespace(customer=SimpleNamespace(username='u', password='p'))
        AtomyQuick(config=current_app.config)._AtomyQuick__login(page, po)
        close_btn.first.click.assert_called_once()

    def test_login_no_popup(self):
        """Login must succeed without error when no popup is present."""
        page, close_btn = self._make_page_mock(has_popup=False)
        po = SimpleNamespace(customer=SimpleNamespace(username='u', password='p'))
        AtomyQuick(config=current_app.config)._AtomyQuick__login(page, po)
        close_btn.first.click.assert_not_called()


# ---------------------------------------------------------------------------
# Integration-style login scenarios — fully mocked (no real browser/network)
# ---------------------------------------------------------------------------

@patch("app.purchase.models.vendors.atomy_quick.sleep", MagicMock())
class TestAtomyQuickLogin(BaseTestCase):
    """Tests for the __login flow covering success and the two alert variants.
    Uses mock Playwright pages so no real browser or credentials are needed."""

    # (outcome, alert_message, username, password, expect_success, label)
    SCENARIOS = [
        ('success', '',                         'any_user', 'pass', True,  'clean login'),
        ('alert',   MESSAGE_REGISTRATION_NEEDED,'reg_user', 'pass', False, 'registration-required alert'),
        ('alert',   'Invalid credentials',      'baduser',  'bad',  False, 'wrong credentials'),
    ]

    def _make_login_page(self, outcome: str, alert_message: str):
        """Return a page mock whose wait_for_function simulates the given outcome.

        outcome='success' → triggered == 'form_gone' (login OK)
        outcome='alert'   → triggered == 'alert', alert locator returns alert_message
        """
        page = MagicMock()

        # Generic locator: count=0 (no blocking popups), page back-ref fixed
        locator = MagicMock()
        locator.count.return_value = 0
        locator.page = page
        if outcome == 'alert':
            locator.first.text_content.return_value = alert_message
        page.locator.return_value = locator

        wff_result = MagicMock()
        wff_result.json_value.return_value = 'form_gone' if outcome == 'success' else 'alert'
        page.wait_for_function.return_value = wff_result
        return page

    def test_login(self):
        for outcome, alert_msg, username, password, expect_success, label in self.SCENARIOS:
            with self.subTest(label=label):
                page = self._make_login_page(outcome, alert_msg)
                vendor = AtomyQuick(logger=logging.getLogger(self.__class__.__name__))
                po = SimpleNamespace(
                    customer=SimpleNamespace(username=username, password=password)
                )
                try:
                    vendor._AtomyQuick__login(page, po)
                    self.assertTrue(
                        expect_success,
                        f"[{label}] expected AtomyLoginError but login succeeded",
                    )
                except AtomyLoginError:
                    self.assertFalse(
                        expect_success,
                        f"[{label}] expected login to succeed but got AtomyLoginError",
                    )
