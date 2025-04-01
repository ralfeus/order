from unittest.mock import MagicMock, patch

import lxml
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
from app.purchase.models.vendors.atomy_quick import AtomyQuick
from app.users.models import Role, User
from exceptions import PurchaseOrderError


def get_json(url, **kwargs):
    url_parts = {
        "overpass-payments/support/mersList": {
            "saleNo": "7012503290010785",
            "mersList": [
                {
                    "payNo": "P2503292181653",
                    "saleNo": "7012503290010785",
                }
            ]
        }
    }

    for url_part, response in url_parts.items():
        if url_part in url:
            return response

def invoke_curl(url, **kwargs) -> tuple[str, str]:
    url_parts = {
        '/goods/goodsResult': '''
        <html>
            <input id="goodsInfo_0" data-goodsinfo="{&quot;goodsNo&quot;: &quot;000000&quot;}" />
        </html>''',
        '/order/finish': 'saleNum: 000, ipgumAccountNo: 456, ipgumAmt: 000'
    }

    for url_part, response in url_parts.items():
        if url_part in url:
            return response, "HTTP/2 200 OK"
    return "", "HTTP/2 200 OK"

def get_html(url, **kwargs):
    return lxml.html.fromstring(invoke_curl(url)[0])
        
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
        self.try_add_entities(
            [
                self.user,
                self.admin,
                admin_role,
                pr.Product(id="000000", name="Test product", price=10, weight=10),
            ]
        )

    @patch("app.purchase.models.vendors.atomy_quick.invoke_curl",
            MagicMock(side_effect=invoke_curl))
    @patch("app.purchase.models.vendors.atomy_quick.get_html",
            MagicMock(side_effect=get_html))
    @patch("app.purchase.models.vendors.atomy_quick:AtomyQuick._AtomyQuick__login",
            MagicMock(return_value=["JSESSIONID=token"]))
    @patch("app.purchase.models.vendors.atomy_quick.get_json",
            MagicMock(side_effect=get_json))
    def test_post_purchase_order(self):
        subcustomer = Subcustomer(username="s1", password="p1")
        order = Order()
        so = Suborder(order)
        op = OrderProduct(suborder=so, product_id="000000", quantity=10)
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
        po = p.PurchaseOrder.query.get(po.id)
        res = AtomyQuick(config=current_app.config).post_purchase_order(po)
        self.assertEqual(res[0].payment_account, "456")

    @patch("app.purchase.models.vendors.atomy_quick.invoke_curl",
            MagicMock(side_effect=invoke_curl))
    @patch("app.purchase.models.vendors.atomy_quick:AtomyQuick._AtomyQuick__login",
            MagicMock(return_value=["JSESSIONID=token"]))
    @patch("app.purchase.models.vendors.atomy_quick.get_json",
            MagicMock(side_effect=get_json))
    @patch("app.purchase.models.vendors.atomy_quick:AtomyQuick._AtomyQuick__get_product_by_id",
            MagicMock(return_value=({'stockExistYn': "N"}, '0000')))
    def test_post_purchase_order_unavailable_product(self):
        subcustomer = Subcustomer(username="s1", password="p1")
        order = Order()
        so = Suborder(order)
        op = OrderProduct(suborder=so, product_id="000000", quantity=10)
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
        po = p.PurchaseOrder.query.get(po.id)
        with self.assertRaises(PurchaseOrderError):
            AtomyQuick(config=current_app.config).post_purchase_order(po)
