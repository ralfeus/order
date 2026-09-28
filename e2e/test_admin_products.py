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
    return db.session.get(Product, product_id).image


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
    product = db.session.get(Product, 'A1')
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
