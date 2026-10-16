'''
Browser tests of purchase order creation (/admin/purchase/orders) for orders
with suborders of several product vendors. PO posting is intercepted to check
what is sent.
'''
import json

import pytest
from playwright.sync_api import BrowserContext, Page, Route, expect

from app import db
from app.currencies.models import Currency
from app.models import Country
from app.models.address import Address
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.order_status import OrderStatus
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.purchase.models.company import Company
from app.settings.models.setting import Setting
from app.users.models.role import Role
from app.users.models.user import User

from conftest import PASSWORD_HASH, login


def _add_order(admin, vendors):
    order = Order(user=admin, status=OrderStatus.can_be_paid, country_id='KR')
    db.session.add(order)
    db.session.commit()
    for vendor in vendors:
        suborder = Suborder(order=order, subcustomer=Subcustomer.query.first())
        db.session.add(suborder)
        db.session.commit()
        db.session.add(OrderProduct(suborder=suborder, product_id=f'{vendor}:0001', quantity=1))
        db.session.commit()
    return order.id


@pytest.fixture
def admin(app):
    user = User(username='po_admin', password_hash=PASSWORD_HASH, enabled=True,
                roles=[Role(name='admin'), Role(name='po-admin')])
    address = Address(id=1, name='Office', zip='00000')
    db.session.add_all([
        Currency(code='KRW', name='Won', rate=1, base=True, enabled=True),
        Country(id='KR', name='Korea', currency_code='KRW', locale='ko-KR'),
        Product(id='0001', vendor='Atomy', name='Atomy 1', price=10, weight=10),
        Product(id='0001', vendor='AtomyAza', name='AZA 1', price=20, weight=10),
        Subcustomer(username='s1', password='p1', name='Sub 1'),
        address,
        Company(id=1, name='Company', address=address, phone='000-0000-0000', enabled=True),
        Setting(key='purchase.default_vendor.AtomyAza', value='AtomyQuick'),
        user,
    ])
    db.session.commit()
    return user


@pytest.fixture
def posted_pos(context: BrowserContext):
    '''Captures PO creation requests instead of sending them to the server'''
    posted = []
    def handle(route: Route):
        if route.request.method != 'POST':
            route.continue_()
            return
        posted.append(json.loads(route.request.post_data))
        route.fulfill(json={'data': []})
    context.route('**/api/v1/admin/purchase/order', handle)
    return posted


def _open_create_form(context: BrowserContext, order_id: str) -> Page:
    login(context, 'po_admin')
    page = context.new_page()
    page.goto(f'/admin/purchase/orders?action=create&order_id={order_id}')
    expect(page.locator('div.DTE')).to_be_visible()
    return page


def _field(page: Page, product_vendor: str):
    return page.locator(f'div.DTE_Field_Name_vendors\\.{product_vendor}')


def test_vendor_per_product_vendor(context: BrowserContext, admin, posted_pos):
    order_id = _add_order(admin, ['Atomy', 'AtomyAza'])
    page = _open_create_form(context, order_id)
    expect(_field(page, 'Atomy')).to_be_visible()
    expect(_field(page, 'AtomyAza')).to_be_visible()
    with page.expect_request(lambda r: r.method == 'POST'
                             and r.url.endswith('/api/v1/admin/purchase/order')):
        # Form opened by URL has no buttons
        page.evaluate('g_create_editor.submit()')
    assert len(posted_pos) == 1
    assert posted_pos[0]['order_id'] == order_id
    assert posted_pos[0]['vendors'] == {'Atomy': 'AtomyQuick', 'AtomyAza': 'AtomyQuick'}


def test_only_vendors_of_order_are_shown(context: BrowserContext, admin, posted_pos):
    order_id = _add_order(admin, ['Atomy'])
    page = _open_create_form(context, order_id)
    expect(_field(page, 'Atomy')).to_be_visible()
    expect(_field(page, 'AtomyAza')).to_be_hidden()
