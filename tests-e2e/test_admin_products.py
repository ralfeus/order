'''
Browser tests of the product picture in the admin product editor (/admin/products).
'''
import base64
import os
import re

import pytest
from playwright.sync_api import BrowserContext, Page, expect

from app import db
from app.currencies.models import Currency
from app.models.file import File
from app.products.models import Product
from app.tools import get_products_path
from app.users.models.role import Role
from app.users.models.user import User

from conftest import PASSWORD_HASH, login

NO_IMAGE = '/static/images/no_image.jpg'
# 1x1 transparent PNG
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')


@pytest.fixture
def admin_page(context: BrowserContext, app) -> Page:
    db.session.add_all([
        # Admin landing page after login needs base currency
        Currency(code='KRW', name='Won', rate=1, base=True, enabled=True),
        User(username='admin', password_hash=PASSWORD_HASH, enabled=True,
             roles=[Role(name='admin')]),
        Product(id='A1', name='Product A', price=100, weight=10),
    ])
    db.session.commit()
    login(context, 'admin')
    page = context.new_page()
    page.goto('/admin/products')
    return page


@pytest.fixture
def cleanup_images():
    paths = []
    yield paths
    for path in paths:
        file = get_products_path(path.split('/products/', 1)[1])
        if os.path.exists(file):
            os.remove(file)


def open_editor(page: Page, product_id: str = 'A1'):
    page.locator('#products tbody tr', has_text=product_id).locator('td').nth(1).click()
    page.get_by_role('button', name='Edit').click()
    expect(page.locator('div.DTE')).to_be_visible()


def submit_editor(page: Page):
    page.locator('div.DTE button', has_text='Update').click()
    expect(page.locator('div.DTE')).to_be_hidden()


def product_image(product_id: str = 'A1'):
    db.session.expire_all()
    return db.session.get(Product, (product_id, 'Atomy')).image


def test_upload_picture(admin_page: Page, cleanup_images):
    open_editor(admin_page)
    expect(admin_page.locator('#image-preview')).to_have_attribute('src', NO_IMAGE)
    expect(admin_page.locator('#image-remove')).to_be_hidden()

    admin_page.locator('#image-file').set_input_files(
        files=[{'name': 'pic.png', 'mimeType': 'image/png', 'buffer': PNG}])
    # Local preview before saving
    expect(admin_page.locator('#image-preview')).to_have_attribute('src', re.compile(r'^blob:'))
    submit_editor(admin_page)

    image = product_image()
    assert image is not None
    cleanup_images.append(image.path)
    assert image.file_name == 'pic.png'

    open_editor(admin_page)
    expect(admin_page.locator('#image-preview')).to_have_attribute('src', image.path)
    expect(admin_page.locator('#image-remove')).to_be_visible()


def test_remove_picture(admin_page: Page):
    product = db.session.get(Product, ('A1', 'Atomy'))
    product.image = File(file_name='old.png', path='/products/old.png')
    db.session.commit()
    admin_page.reload()

    open_editor(admin_page)
    expect(admin_page.locator('#image-preview')).to_have_attribute('src', '/products/old.png')
    admin_page.locator('#image-remove').click()
    expect(admin_page.locator('#image-preview')).to_have_attribute('src', NO_IMAGE)
    submit_editor(admin_page)

    assert product_image() is None


def test_too_large_picture_is_rejected(admin_page: Page):
    open_editor(admin_page)
    admin_page.locator('#image-file').set_input_files(files=[{
        'name': 'big.png', 'mimeType': 'image/png',
        'buffer': b'0' * (5 * 1024 * 1024 + 1)}])

    expect(admin_page.locator('.modal-title')).to_have_text('Product picture')
    expect(admin_page.locator('#image-preview')).to_have_attribute('src', NO_IMAGE)
    expect(admin_page.locator('#image-file')).to_have_value('')


@pytest.fixture
def shared_id_page(admin_page: Page) -> Page:
    '''Products of two vendors with the same ID'''
    db.session.add(Product(id='A1', vendor='AtomyAza', name='AZA product', price=200))
    db.session.commit()
    admin_page.reload()
    expect(admin_page.locator('#products tbody tr')).to_have_count(2)
    return admin_page


def product(key: str):
    db.session.expire_all()
    return Product.get_by_key(key)


def row(page: Page, text: str):
    return page.locator('#products tbody tr', has_text=text)


def test_name_shows_vendor(admin_page: Page):
    expect(row(admin_page, 'Product A').locator('td').nth(2)).to_have_text(
        '(Atomy) Product A')


def test_edit_product_of_vendor_with_shared_id(shared_id_page: Page):
    row(shared_id_page, '(AtomyAza)').locator('td').nth(1).click()
    shared_id_page.get_by_role('button', name='Edit').click()
    expect(shared_id_page.locator('div.DTE')).to_be_visible()
    shared_id_page.locator('div.DTE input[id$="_name"]').first.fill('AZA renamed')
    submit_editor(shared_id_page)

    assert product('AtomyAza:A1').name == 'AZA renamed'
    assert product('Atomy:A1').name == 'Product A'
    expect(row(shared_id_page, '(AtomyAza)').locator('td').nth(2)).to_have_text(
        '(AtomyAza) AZA renamed')


def test_picture_of_vendor_with_shared_id(shared_id_page: Page, cleanup_images):
    row(shared_id_page, '(AtomyAza)').locator('td').nth(1).click()
    shared_id_page.get_by_role('button', name='Edit').click()
    shared_id_page.locator('#image-file').set_input_files(
        files=[{'name': 'pic.png', 'mimeType': 'image/png', 'buffer': PNG}])
    submit_editor(shared_id_page)

    image = product('AtomyAza:A1').image
    assert image is not None
    cleanup_images.append(image.path)
    assert product('Atomy:A1').image is None


def test_details_save_of_vendor_with_shared_id(shared_id_page: Page):
    row(shared_id_page, '(AtomyAza)').locator('td.details-control').click()
    details = shared_id_page.locator('tr:not(.shown) .product-details')
    expect(details).to_be_visible()
    details.locator('#name_english').fill('AZA english')
    details.locator('.btn-save').click()

    expect(row(shared_id_page, '(AtomyAza)').locator('td').nth(3)).to_have_text('AZA english')
    assert product('AtomyAza:A1').name_english == 'AZA english'
    assert product('Atomy:A1').name_english is None


def test_delete_product_of_vendor_with_shared_id(shared_id_page: Page):
    row(shared_id_page, '(AtomyAza)').locator('td').nth(1).click()
    shared_id_page.get_by_role('button', name='Delete').click()
    shared_id_page.locator('div.DTE button', has_text='Delete').click()
    expect(row(shared_id_page, '(AtomyAza)')).to_have_count(0)

    assert product('AtomyAza:A1') is None
    assert product('Atomy:A1') is not None


def _field(page: Page, name: str):
    return page.locator(f'div.DTE_Field_Name_{name}')


def test_create_product_of_vendor(admin_page: Page):
    admin_page.get_by_role('button', name='Create').click()
    expect(admin_page.locator('div.DTE')).to_be_visible()
    expect(_field(admin_page, 'vendor').locator('select')).to_have_value('Atomy')
    _field(admin_page, 'id').locator('input').fill('A1')
    _field(admin_page, 'vendor').locator('select').select_option('AtomyAza')
    _field(admin_page, 'name').locator('input').fill('New AZA product')
    admin_page.locator('div.DTE button', has_text='Create').click()
    expect(admin_page.locator('div.DTE')).to_be_hidden()

    assert product('AtomyAza:A1').name == 'New AZA product'
    assert product('Atomy:A1').name == 'Product A'
    expect(row(admin_page, '(AtomyAza)').locator('td').nth(2)).to_have_text(
        '(AtomyAza) New AZA product')


def test_create_existing_product_shows_error(admin_page: Page):
    admin_page.get_by_role('button', name='Create').click()
    _field(admin_page, 'id').locator('input').fill('A1')
    admin_page.locator('div.DTE button', has_text='Create').click()
    expect(admin_page.locator('.modal', has_text='already exists')).to_be_visible()
    assert product('Atomy:A1').name == 'Product A'


def test_vendor_isnt_editable(admin_page: Page):
    open_editor(admin_page)
    expect(_field(admin_page, 'vendor').locator('select')).to_have_value('Atomy')
    expect(_field(admin_page, 'vendor').locator('select')).to_be_disabled()
