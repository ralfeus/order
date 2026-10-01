'''
Browser tests of warehouse products (/admin/warehouses/<id>) of several vendors
having the same product ID
'''
import pytest
from playwright.sync_api import BrowserContext, Page, expect

from app import db
from app.currencies.models import Currency
from app.modules.warehouse.models.warehouse import Warehouse, WarehouseProduct
from app.products.models import Product
from app.users.models.role import Role
from app.users.models.user import User

from conftest import PASSWORD_HASH, login


@pytest.fixture
def warehouse_page(context: BrowserContext, app) -> Page:
    warehouse = Warehouse(id=1, name='W1')
    db.session.add_all([
        Currency(code='KRW', name='Won', rate=1, base=True, enabled=True),
        User(username='admin', password_hash=PASSWORD_HASH, enabled=True,
             roles=[Role(name='admin')]),
        Product(id='A1', vendor='Atomy', name='Atomy product'),
        Product(id='A1', vendor='AtomyAza', name='AZA product'),
        warehouse,
    ])
    db.session.commit()
    db.session.add_all([
        WarehouseProduct(warehouse=warehouse, product_id='Atomy:A1', quantity=1),
        WarehouseProduct(warehouse=warehouse, product_id='AtomyAza:A1', quantity=2),
    ])
    db.session.commit()
    login(context, 'admin')
    page = context.new_page()
    page.goto('/admin/warehouses/1')
    expect(page.locator('#warehouse_products tbody tr')).to_have_count(2)
    return page


def stock():
    db.session.expire_all()
    return {wp.product.key: wp.quantity for wp in WarehouseProduct.query}


def row(page: Page, text: str):
    return page.locator('#warehouse_products tbody tr', has_text=text)


def test_rows_show_vendor(warehouse_page: Page):
    expect(row(warehouse_page, 'AZA product')).to_contain_text('(AtomyAza) AZA product')
    expect(row(warehouse_page, 'Atomy product')).to_contain_text('(Atomy) Atomy product')


def test_edit_quantity_of_vendor_with_shared_id(warehouse_page: Page):
    row(warehouse_page, 'AZA product').locator('td').nth(2).click()
    warehouse_page.get_by_role('button', name='Edit').click()
    editor = warehouse_page.locator('div.DTE')
    expect(editor).to_be_visible()
    editor.locator('input[id$="_quantity"]').fill('7')
    editor.locator('button', has_text='Update').click()
    expect(editor).to_be_hidden()

    assert stock() == {'Atomy:A1': 1, 'AtomyAza:A1': 7}


def test_delete_product_of_vendor_with_shared_id(warehouse_page: Page):
    row(warehouse_page, 'AZA product').locator('td').nth(2).click()
    warehouse_page.get_by_role('button', name='Delete').click()
    warehouse_page.locator('div.DTE button', has_text='Delete').click()
    expect(row(warehouse_page, 'AZA product')).to_have_count(0)

    assert stock() == {'Atomy:A1': 1}
