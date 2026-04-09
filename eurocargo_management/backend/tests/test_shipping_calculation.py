"""Tests for carrier cost calculation logic."""
from decimal import Decimal

import pytest

from app.carriers.gls import GLSCarrier
from app.models.shipping_rate import ShippingFlatRate, ShippingRateEntry


@pytest.fixture
def flat_rate(db_session):
    r = ShippingFlatRate(rate_per_kg=Decimal('12.00'))
    db_session.add(r)
    db_session.flush()
    return r


@pytest.fixture
def de_rates(db_session):
    entries = [
        ShippingRateEntry(shipment_type_code='GLS', country='DE',
                          max_weight_kg=Decimal('3.000'), cost=Decimal('3.00')),
        ShippingRateEntry(shipment_type_code='GLS', country='DE',
                          max_weight_kg=Decimal('5.000'), cost=Decimal('4.00')),
    ]
    for e in entries:
        db_session.add(e)
    db_session.flush()
    return entries


@pytest.fixture
def carrier(db_session):
    c = GLSCarrier(code='GLS', name='Galaxus', enabled=True)
    db_session.add(c)
    db_session.flush()
    return c


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------

def test_2kg_to_germany(carrier, flat_rate, de_rates, db_session):
    # 12.00 × 2 + 3.00 (≤3 kg tier) = 27.00
    cost = carrier.calculate_cost(Decimal('2.000'), 'DE', db_session)
    assert cost == Decimal('27.00')


def test_3kg_to_germany_uses_exact_tier(carrier, flat_rate, de_rates, db_session):
    # 12.00 × 3 + 3.00 (≤3 kg tier, exact match) = 39.00
    cost = carrier.calculate_cost(Decimal('3.000'), 'DE', db_session)
    assert cost == Decimal('39.00')


def test_4kg_to_germany_uses_next_tier(carrier, flat_rate, de_rates, db_session):
    # 12.00 × 4 + 4.00 (≤5 kg tier) = 52.00
    cost = carrier.calculate_cost(Decimal('4.000'), 'DE', db_session)
    assert cost == Decimal('52.00')


def test_fractional_weight(carrier, flat_rate, de_rates, db_session):
    # 12.00 × 1.5 + 3.00 = 21.00
    cost = carrier.calculate_cost(Decimal('1.500'), 'DE', db_session)
    assert cost == Decimal('21.00')


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_no_flat_rate_raises(carrier, db_session):
    with pytest.raises(ValueError, match='No flat rate'):
        carrier.calculate_cost(Decimal('2.000'), 'DE', db_session)


def test_unknown_country_raises(carrier, flat_rate, de_rates, db_session):
    with pytest.raises(ValueError, match='No rate for'):
        carrier.calculate_cost(Decimal('2.000'), 'FR', db_session)


def test_weight_exceeds_max_tier_raises(carrier, flat_rate, de_rates, db_session):
    # 6 kg exceeds the 5 kg max entry for DE
    with pytest.raises(ValueError, match='No rate for'):
        carrier.calculate_cost(Decimal('6.000'), 'DE', db_session)


def test_no_rate_entries_raises(carrier, flat_rate, db_session):
    with pytest.raises(ValueError, match='No rate for'):
        carrier.calculate_cost(Decimal('2.000'), 'DE', db_session)
