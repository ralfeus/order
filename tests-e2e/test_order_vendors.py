'''
Browser tests of the order form (/orders/new) with products of several vendors
having the same product ID. Order posting is intercepted to check what is sent.
'''
import json
import re

import pytest
from playwright.sync_api import BrowserContext, Page, Route, expect

from app import db
from app.currencies.models import Currency
from app.models import Country
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.order_status import OrderStatus
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.shipping.models.shipping import NoShipping, Shipping, ShippingRate
from app.users.models.user import User

from conftest import PASSWORD_HASH, login


@pytest.fixture
def user(app):
    buyer = User(username='buyer', password_hash=PASSWORD_HASH, enabled=True)
    db.session.add_all([
        Currency(code='KRW', name='Won', rate=1, base=True, enabled=True),
        Country(id='KR', name='Korea', currency_code='KRW', locale='ko-KR'),
        Shipping(id=1, name='Cargo', enabled=True),
        ShippingRate(shipping_method_id=1, destination='KR', weight=100000, rate=100),
        NoShipping(id=999, enabled=True),
        Product(id='0001', vendor='Atomy', name='Atomy 1', price=10, weight=10),
        Product(id='0001', vendor='AtomyAza', name='AZA 1', price=20, weight=10),
        Product(id='Z9', vendor='AtomyAza', name='AZA Z9', price=30, weight=10),
        buyer,
    ])
    db.session.commit()
    return buyer


@pytest.fixture
def posted_orders(context: BrowserContext):
    '''Captures order posting requests instead of sending them to the server'''
    posted = []
    def handle(route: Route):
        posted.append(json.loads(route.request.post_data))
        route.fulfill(json={'status': 'updated', 'order_id': 'ORD-TEST'})
    context.route('**/api/v1/order', handle)
    context.route('**/api/v1/order/ORD-*', lambda route: handle(route)
                  if route.request.method == 'POST' else route.continue_())
    return posted


@pytest.fixture
def order_page(context: BrowserContext, user, posted_orders) -> Page:
    login(context, 'buyer')
    page = context.new_page()
    page.goto('/orders/new')
    return page


def first_row(page: Page):
    return page.locator('tr.item').first


def type_code(page: Page, code: str):
    row = first_row(page)
    row.locator('.item-code').fill(code)
    row.locator('.item-code').press('Tab')


def submit(page: Page, posted):
    page.locator('#submit').click()
    page.wait_for_function('() => true')
    expect(page.locator('.modal-title')).to_be_visible()
    return posted[-1]['suborders'][0]['items']


def test_unique_code_shows_vendor(order_page: Page, posted_orders):
    type_code(order_page, 'Z9')
    expect(first_row(order_page).locator('.item-name')).to_contain_text('(AtomyAza) AZA Z9')
    items = submit(order_page, posted_orders)
    assert items[0]['item_code'] == 'Z9'
    assert items[0]['product_key'] == 'AtomyAza:Z9'


def test_ambiguous_code_offers_choice(order_page: Page, posted_orders):
    type_code(order_page, '1')
    chooser = first_row(order_page).locator('select.product-chooser')
    expect(chooser).to_be_visible()
    expect(chooser.locator('option')).to_have_text(
        ['Choose product...', '(Atomy) Atomy 1', '(AtomyAza) AZA 1'])
    expect(first_row(order_page).locator('.item-code')).to_have_class(
        re.compile('is-invalid'))

    chooser.select_option('AtomyAza:0001')
    expect(first_row(order_page).locator('.item-name')).to_contain_text('(AtomyAza) AZA 1')
    expect(first_row(order_page).locator('.item-price')).not_to_be_empty()
    items = submit(order_page, posted_orders)
    assert items[0]['product_key'] == 'AtomyAza:0001'


def test_changed_code_doesnt_keep_old_product(order_page: Page, posted_orders):
    type_code(order_page, '1')
    first_row(order_page).locator('select.product-chooser').select_option('AtomyAza:0001')
    type_code(order_page, 'Z9')
    expect(first_row(order_page).locator('.item-name')).to_contain_text('(AtomyAza) AZA Z9')
    items = submit(order_page, posted_orders)
    assert items[0]['product_key'] == 'AtomyAza:Z9'


def test_unresolved_choice_sends_no_key(order_page: Page, posted_orders):
    type_code(order_page, '1')
    expect(first_row(order_page).locator('select.product-chooser')).to_be_visible()
    items = submit(order_page, posted_orders)
    assert items[0]['item_code'] == '1'
    assert not items[0].get('product_key')


def test_draft_order_keeps_vendor(context: BrowserContext, user, posted_orders):
    order = Order(id='ORD-DRAFT', user=user, status=OrderStatus.draft,
                  country_id='KR', shipping_method_id=1)
    subcustomer = Subcustomer(name='Sub', username='S0001')
    suborder = Suborder(order=order, subcustomer=subcustomer)
    db.session.add_all([order, subcustomer, suborder])
    db.session.commit()
    db.session.add(OrderProduct(suborder=suborder, product_id='AtomyAza:0001', quantity=2))
    db.session.commit()
    login(context, 'buyer')
    page = context.new_page()
    page.goto('/orders/ORD-DRAFT')
    expect(first_row(page).locator('.item-name')).to_contain_text('(AtomyAza) AZA 1')
    expect(first_row(page).locator('.item-code')).to_have_value('0001')
    items = submit(page, posted_orders)
    assert items[0]['product_key'] == 'AtomyAza:0001'
