'''
Browser tests of the end-user product catalog (/catalog).

Shipping rates are stubbed in the browser (the catalog page requests them from
/api/v1/shipping/rate/...), so no external service is called.
Base currency is KRW, user's currency is USD at 0.001, 10kg EMS parcel costs
50 000 KRW to DE and 80 000 KRW to FR, 10kg Cargo parcel costs 30 000 KRW
to DE and there is no Cargo delivery to FR.
'''
import json
import re

import pytest
from playwright.sync_api import BrowserContext, Page, Route, expect

from app import db
from app.currencies.models import Currency
from app.models import Country
from app.products.models import Product
from app.shipping.methods.ems.models.ems import EMS
from app.shipping.models.shipping import NoShipping, Shipping
from app.users.models.user import User

from conftest import PASSWORD_HASH, login

EMS_ID = 7
CARGO_ID = 8
PARCEL_RATES = {'DE': 50000, 'FR': 80000}
CARGO_RATES = {'DE': 30000}
RATE_URL = re.compile(r'/api/v1/shipping/rate/(\w+)/(\d+)/\d+$')


@pytest.fixture
def user(app):
    db.session.add_all([
        Currency(code='KRW', name='Won', rate=1, base=True, enabled=True),
        Currency(code='USD', name='Dollar', rate=0.001, enabled=True),
        Country(id='KR', name='Korea', currency_code='KRW', locale='ko-KR', sort_order=3),
        Country(id='DE', name='Germany', currency_code='EUR', sort_order=1),
        Country(id='FR', name='France', currency_code='EUR', sort_order=2),
        EMS(id=EMS_ID, name='EMS', enabled=True),
        Shipping(id=CARGO_ID, name='Cargo', enabled=True),
        Shipping(id=9, name='Disabled', enabled=False),
        NoShipping(id=10, enabled=True),
        Product(id='A1', name='상품', name_english='Product A', price=10000, weight=500),
        Product(id='B2', name='Product B', price=5000, weight=0),
        Product(id='C3', name='Product C', price=1000, weight=100, available=False),
    ])
    catalog_user = User(username='buyer', password_hash=PASSWORD_HASH, enabled=True,
                        currency_code='USD')
    db.session.add(catalog_user)
    db.session.commit()
    return catalog_user


@pytest.fixture
def catalog(context: BrowserContext, user):
    login(context, user.username)
    return context


def stub_rates(page: Page, rates=PARCEL_RATES, cargo_rates=CARGO_RATES):
    def handle(route: Route):
        country, shipping = RATE_URL.search(route.request.url).groups()
        rates_by = rates if int(shipping) == EMS_ID else cargo_rates
        if country in rates_by:
            route.fulfill(json={'shipping_cost': rates_by[country]})
        else:
            route.fulfill(status=409, body=f'No rate to {country}')
    page.route(RATE_URL, handle)


def row(page: Page, product_id: str):
    return page.locator('#catalog tbody tr', has_text=f'#{product_id}')


def expect_prices(page: Page, product_id: str, price, delivery, total, recommended):
    cells = row(page, product_id)
    expect(cells.locator('td.money-price')).to_have_text(price)
    expect(cells.locator('td.money-delivery')).to_have_text(delivery)
    expect(cells.locator('td.money-total')).to_have_text(total)
    expect(cells.locator('td.money-recommended')).to_have_text(recommended)


def profile_of(user: User) -> dict:
    db.session.expire_all()
    return db.session.get(User, user.id).get_profile()


def test_catalog_shows_prices_in_user_currency(catalog, page: Page):
    stub_rates(page)
    page.goto('/catalog')

    expect(page.locator('#catalog-country')).to_have_value('DE')
    # EMS is preselected even though it's not first; disabled and
    # "no shipping" methods are not offered
    shipping = page.locator('#catalog-shipping')
    expect(shipping).to_have_value(str(EMS_ID))
    expect(shipping.locator('option')).to_have_text(['Cargo', 'EMS'])
    expect(row(page, 'A1')).to_contain_text('Product A')
    # 10 000 KRW + 50 000 * 500g / 10kg = 12 500 KRW -> USD
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')
    expect(row(page, 'C3')).to_have_count(0)
    expect(page.locator('#catalog-alert')).to_be_hidden()


def test_product_without_weight(catalog, page: Page):
    stub_rates(page)
    page.goto('/catalog')

    expect_prices(page, 'B2', '$5.00', '—', '$5.00', '$5.00')


def test_markup_change_recalculates_and_saves(catalog, page: Page, user):
    stub_rates(page)
    page.goto('/catalog')
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')

    markup = page.locator('#catalog-markup')
    with page.expect_response('**/api/v1/user/preferences') as response:
        markup.fill('1.5')
        markup.blur()
    assert response.value.ok

    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$18.75')
    assert profile_of(user)['catalog_markup'] == 1.5


def test_invalid_markup_is_rejected(catalog, page: Page, user):
    stub_rates(page)
    saved = []
    page.on('request', lambda request: saved.append(request)
            if '/api/v1/user/preferences' in request.url else None)
    page.goto('/catalog')
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')

    markup = page.locator('#catalog-markup')
    markup.fill('0')
    markup.blur()

    expect(markup).to_have_class(re.compile(r'\bis-invalid\b'))
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')
    assert saved == []
    assert 'catalog_markup' not in profile_of(user)


def test_country_change_recalculates_and_saves(catalog, page: Page, user):
    stub_rates(page)
    page.goto('/catalog')
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')

    with page.expect_response('**/api/v1/user/preferences') as response, \
         page.expect_request(re.compile(r'/rate/FR/')):
        page.locator('#catalog-country').select_option('FR')
    assert response.value.ok

    # 10 000 KRW + 80 000 * 500g / 10kg = 14 000 KRW -> USD
    expect_prices(page, 'A1', '$10.00', '$4.00', '$14.00', '$14.00')
    assert profile_of(user)['catalog_country'] == 'FR'


def test_no_rate_to_country(catalog, page: Page):
    stub_rates(page, rates={})
    page.goto('/catalog')

    alert = page.locator('#catalog-alert')
    expect(alert).to_be_visible()
    expect(alert).to_contain_text('no EMS delivery to Germany')
    expect_prices(page, 'A1', '$10.00', 'n/a', 'n/a', 'n/a')
    expect(row(page, 'A1').locator('td.money-delivery span')).to_have_attribute(
        'title', "EMS doesn't deliver to Germany")


def test_shipping_change_recalculates_and_saves(catalog, page: Page, user):
    stub_rates(page)
    page.goto('/catalog')
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')

    with page.expect_response('**/api/v1/user/preferences') as response, \
         page.expect_request(re.compile(rf'/rate/DE/{CARGO_ID}/')):
        page.locator('#catalog-shipping').select_option(str(CARGO_ID))
    assert response.value.ok

    # 10 000 KRW + 30 000 * 500g / 10kg = 11 500 KRW -> USD
    expect_prices(page, 'A1', '$10.00', '$1.50', '$11.50', '$11.50')
    assert profile_of(user)['catalog_shipping'] == CARGO_ID


def test_unavailable_shipping_and_country_combination(catalog, page: Page):
    stub_rates(page)
    page.goto('/catalog')
    page.locator('#catalog-shipping').select_option(str(CARGO_ID))
    expect_prices(page, 'A1', '$10.00', '$1.50', '$11.50', '$11.50')

    page.locator('#catalog-country').select_option('FR')

    expect_prices(page, 'A1', '$10.00', 'n/a', 'n/a', 'n/a')
    expect(row(page, 'A1').locator('td.money-delivery span')).to_have_attribute(
        'title', "Cargo doesn't deliver to France")
    alert = page.locator('#catalog-alert')
    expect(alert).to_be_visible()
    expect(alert).to_contain_text('no Cargo delivery to France')

    # Switching to an available combination clears the unavailability
    page.locator('#catalog-shipping').select_option(str(EMS_ID))
    expect_prices(page, 'A1', '$10.00', '$4.00', '$14.00', '$14.00')
    expect(alert).to_be_hidden()


def test_saved_preferences_are_applied(catalog, page: Page, user):
    user.set_profile({'catalog_country': 'DE', 'catalog_markup': 2,
                      'catalog_shipping': CARGO_ID})
    db.session.commit()
    stub_rates(page)

    with page.expect_request(re.compile(rf'/rate/DE/{CARGO_ID}/')):
        page.goto('/catalog')

    expect(page.locator('#catalog-country')).to_have_value('DE')
    expect(page.locator('#catalog-shipping')).to_have_value(str(CARGO_ID))
    expect(page.locator('#catalog-markup')).to_have_value('2')
    expect_prices(page, 'A1', '$10.00', '$1.50', '$11.50', '$23.00')


def test_saved_shipping_no_longer_available(catalog, page: Page, user):
    '''Saved shipping method was disabled since - EMS is used instead'''
    user.set_profile({'catalog_shipping': 9})
    db.session.commit()
    stub_rates(page)

    with page.expect_request(re.compile(rf'/rate/DE/{EMS_ID}/')):
        page.goto('/catalog')

    expect(page.locator('#catalog-shipping')).to_have_value(str(EMS_ID))
    expect_prices(page, 'A1', '$10.00', '$2.50', '$12.50', '$12.50')


def test_stale_rate_response_is_ignored(catalog, page: Page):
    '''The rate for a previously selected country arrives after the rate
    for the newly selected one and must not overwrite it'''
    pending: list[Route] = []

    def handle(route: Route):
        country = RATE_URL.search(route.request.url).group(1)
        if country == 'DE':
            pending.append(route)  # hold the response back
        else:
            route.fulfill(json={'shipping_cost': PARCEL_RATES[country]})
    page.route(RATE_URL, handle)

    with page.expect_request(re.compile(r'/rate/DE/')):
        page.goto('/catalog')
    page.locator('#catalog-country').select_option('FR')
    expect_prices(page, 'A1', '$10.00', '$4.00', '$14.00', '$14.00')

    with page.expect_response(re.compile(r'/rate/DE/')):
        pending[0].fulfill(body=json.dumps({'shipping_cost': PARCEL_RATES['DE']}),
                           content_type='application/json')
    # Negative check: give the page a moment to (wrongly) apply the stale rate
    page.wait_for_timeout(300)
    expect_prices(page, 'A1', '$10.00', '$4.00', '$14.00', '$14.00')


def test_no_shipping_methods_enabled(catalog, page: Page):
    for shipping_id in (EMS_ID, CARGO_ID):
        db.session.get(Shipping, shipping_id).enabled = False
    db.session.commit()
    stub_rates(page)
    page.goto('/catalog')

    expect(page.locator('#catalog-shipping')).to_be_disabled()
    expect(page.locator('#catalog-shipping option')).to_have_count(0)
    alert = page.locator('#catalog-alert')
    expect(alert).to_be_visible()
    expect(alert).to_contain_text('No shipping methods are available')
    expect_prices(page, 'A1', '$10.00', 'n/a', 'n/a', 'n/a')


def test_stale_rate_response_after_shipping_change_is_ignored(catalog, page: Page):
    '''The EMS rate arrives after the Cargo rate was selected and applied
    and must not overwrite it'''
    pending: list[Route] = []

    def handle(route: Route):
        country, shipping = RATE_URL.search(route.request.url).groups()
        if int(shipping) == EMS_ID:
            pending.append(route)  # hold the response back
        else:
            route.fulfill(json={'shipping_cost': CARGO_RATES[country]})
    page.route(RATE_URL, handle)

    with page.expect_request(re.compile(rf'/rate/DE/{EMS_ID}/')):
        page.goto('/catalog')
    page.locator('#catalog-shipping').select_option(str(CARGO_ID))
    expect_prices(page, 'A1', '$10.00', '$1.50', '$11.50', '$11.50')

    with page.expect_response(re.compile(rf'/rate/DE/{EMS_ID}/')):
        pending[0].fulfill(body=json.dumps({'shipping_cost': PARCEL_RATES['DE']}),
                           content_type='application/json')
    # Negative check: give the page a moment to (wrongly) apply the stale rate
    page.wait_for_timeout(300)
    expect_prices(page, 'A1', '$10.00', '$1.50', '$11.50', '$11.50')


def test_rate_network_error(catalog, page: Page):
    '''Network failure isn't an unavailable combination - no tooltip about it'''
    page.route(RATE_URL, lambda route: route.abort())
    page.goto('/catalog')

    alert = page.locator('#catalog-alert')
    expect(alert).to_be_visible()
    expect(alert).to_contain_text('Try again later')
    expect_prices(page, 'A1', '$10.00', 'n/a', 'n/a', 'n/a')
    expect(row(page, 'A1').locator('td.money-delivery span')).not_to_have_attribute(
        'title', re.compile('.*'))


def test_shipping_name_is_escaped(catalog, page: Page):
    db.session.add(Shipping(id=11, name='<b>Bold</b>', enabled=True))
    db.session.commit()
    stub_rates(page, cargo_rates={})
    page.goto('/catalog')

    option = page.locator('#catalog-shipping option[value="11"]')
    expect(option).to_have_text('<b>Bold</b>')
    page.locator('#catalog-shipping').select_option('11')

    delivery = row(page, 'A1').locator('td.money-delivery')
    expect(delivery.locator('span')).to_have_attribute(
        'title', "<b>Bold</b> doesn't deliver to Germany")
    expect(delivery.locator('b')).to_have_count(0)
    alert = page.locator('#catalog-alert')
    expect(alert).to_contain_text('no <b>Bold</b> delivery to Germany')
    expect(alert.locator('b')).to_have_count(0)
