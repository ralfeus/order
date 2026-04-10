"""Tests for admin rate table and multiplier endpoints."""
from decimal import Decimal

import pytest

from app.models.shipping_rate import ShippingRateEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rate_entries(db_session, shipment_type):
    """Seed a small rate table for GLS: 2 countries × 2 weight tiers."""
    entries = [
        ShippingRateEntry(shipment_type_code='GLS', country='DE',
                          max_weight_kg=Decimal('5.000'), cost=Decimal('4.00')),
        ShippingRateEntry(shipment_type_code='GLS', country='DE',
                          max_weight_kg=Decimal('10.000'), cost=Decimal('7.00')),
        ShippingRateEntry(shipment_type_code='GLS', country='CZ',
                          max_weight_kg=Decimal('5.000'), cost=Decimal('5.00')),
        ShippingRateEntry(shipment_type_code='GLS', country='CZ',
                          max_weight_kg=Decimal('10.000'), cost=Decimal('9.00')),
    ]
    for e in entries:
        db_session.add(e)
    db_session.flush()
    return entries


# ---------------------------------------------------------------------------
# GET /api/v1/admin/rates
# ---------------------------------------------------------------------------

def test_list_rates_returns_carrier(admin_client, shipment_type, rate_entries):
    res = admin_client.get('/api/v1/admin/rates')
    assert res.status_code == 200
    data = res.json()
    codes = [c['code'] for c in data]
    assert 'GLS' in codes


def test_list_rates_includes_entries(admin_client, shipment_type, rate_entries):
    res = admin_client.get('/api/v1/admin/rates')
    carrier = next(c for c in res.json() if c['code'] == 'GLS')
    assert len(carrier['entries']) == 4


def test_list_rates_default_multiplier(admin_client, shipment_type):
    res = admin_client.get('/api/v1/admin/rates')
    carrier = next(c for c in res.json() if c['code'] == 'GLS')
    assert Decimal(carrier['multiplier']) == Decimal('1.0')


def test_list_rates_requires_admin(regular_client):
    res = regular_client.get('/api/v1/admin/rates')
    assert res.status_code == 403


def test_list_rates_requires_auth(client):
    res = client.get('/api/v1/admin/rates')
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/admin/rates/{carrier_code}
# ---------------------------------------------------------------------------

def test_get_carrier_rates(admin_client, shipment_type, rate_entries):
    res = admin_client.get('/api/v1/admin/rates/GLS')
    assert res.status_code == 200
    data = res.json()
    assert data['code'] == 'GLS'
    assert len(data['entries']) == 4


def test_get_carrier_rates_not_found(admin_client):
    res = admin_client.get('/api/v1/admin/rates/UNKNOWN')
    assert res.status_code == 404


def test_get_carrier_rates_entries_sorted(admin_client, shipment_type, rate_entries):
    """Entries come back sorted by country then weight."""
    res = admin_client.get('/api/v1/admin/rates/GLS')
    entries = res.json()['entries']
    countries = [e['country'] for e in entries]
    assert countries == sorted(countries)


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/rates/{carrier_code}/multiplier
# ---------------------------------------------------------------------------

def test_update_multiplier(admin_client, shipment_type):
    res = admin_client.patch(
        '/api/v1/admin/rates/GLS/multiplier',
        json={'multiplier': '1.5'},
    )
    assert res.status_code == 200
    assert Decimal(res.json()['multiplier']) == Decimal('1.5')


def test_update_multiplier_reflected_in_get(admin_client, shipment_type):
    admin_client.patch('/api/v1/admin/rates/GLS/multiplier', json={'multiplier': '2.0'})
    res = admin_client.get('/api/v1/admin/rates/GLS')
    assert Decimal(res.json()['multiplier']) == Decimal('2.0')


def test_update_multiplier_zero_rejected(admin_client, shipment_type):
    res = admin_client.patch(
        '/api/v1/admin/rates/GLS/multiplier',
        json={'multiplier': '0'},
    )
    assert res.status_code == 422


def test_update_multiplier_negative_rejected(admin_client, shipment_type):
    res = admin_client.patch(
        '/api/v1/admin/rates/GLS/multiplier',
        json={'multiplier': '-0.5'},
    )
    assert res.status_code == 422


def test_update_multiplier_not_found(admin_client):
    res = admin_client.patch(
        '/api/v1/admin/rates/GHOST/multiplier',
        json={'multiplier': '1.2'},
    )
    assert res.status_code == 404


def test_update_multiplier_requires_admin(regular_client, shipment_type):
    res = regular_client.patch(
        '/api/v1/admin/rates/GLS/multiplier',
        json={'multiplier': '1.5'},
    )
    assert res.status_code == 403


def test_multiplier_affects_calculate_cost(db_session, shipment_type, rate_entries):
    """Carrier.calculate_cost() uses the multiplier."""
    from app.models.shipping_rate import ShippingFlatRate
    db_session.add(ShippingFlatRate(rate_per_kg=Decimal('10.00')))
    db_session.flush()

    carrier = shipment_type   # GLSCarrier with default multiplier=1
    base_cost = carrier.calculate_cost(Decimal('3.000'), 'DE', db_session)

    carrier.multiplier = Decimal('2.0')
    db_session.flush()
    doubled_cost = carrier.calculate_cost(Decimal('3.000'), 'DE', db_session)

    # flat part stays same; table part doubles
    assert doubled_cost > base_cost
    # table entry for DE ≤5kg = 4.00 → doubled = 8.00; flat = 10*3 = 30
    assert base_cost == Decimal('34.00')    # 30 + 4
    assert doubled_cost == Decimal('38.00') # 30 + 8
