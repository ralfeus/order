"""Tests for POST/GET /api/v1/shipments/{token}/invoice[/pdf]."""
from decimal import Decimal

import pytest

from app.models.config import Config
from app.models.invoice import Invoice
from app.models.shipment import Shipment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def configured_db(db_session):
    """Seed config table with all required recipient settings."""
    entries = [
        Config(name='invoice_prefix',      value='INV'),
        Config(name='recipient_name',      value='EuroCargo GmbH'),
        Config(name='recipient_address',   value='Hauptstraße 1, 10115 Berlin, Germany'),
        Config(name='recipient_vat',       value='DE123456789'),
        Config(name='recipient_iban',      value='DE89370400440532013000'),
        Config(name='recipient_bic',       value='COBADEFFXXX'),
        Config(name='recipient_bank_name', value='Commerzbank'),
    ]
    for e in entries:
        db_session.add(e)
    db_session.flush()
    return db_session


@pytest.fixture
def priced_shipment(db_session, shipment_type):
    s = Shipment(
        order_id='ORD-INV-0001',
        customer_name='Invoice Tester',
        email='invoice@example.com',
        address='1 Invoice Lane',
        city='Hamburg',
        country='DE',
        zip='20095',
        shipment_type_id=shipment_type.id,
        weight_kg=Decimal('2.000'),
        amount_eur=Decimal('28.00'),
    )
    db_session.add(s)
    db_session.flush()
    return s


# ---------------------------------------------------------------------------
# POST /api/v1/shipments/{token}/invoice
# ---------------------------------------------------------------------------

def test_generate_invoice_success(client, priced_shipment, configured_db):
    res = client.post(f'/api/v1/shipments/{priced_shipment.token}/invoice')
    assert res.status_code == 201
    data = res.json()
    assert data['invoice_number'].startswith('INV-')
    assert data['iban'] == 'DE89370400440532013000'
    assert data['bic'] == 'COBADEFFXXX'
    assert data['amount_eur'] == '28.00'
    assert data['reference'] == data['invoice_number']


def test_generate_invoice_idempotent(client, priced_shipment, configured_db):
    """Calling POST twice returns the same invoice number."""
    res1 = client.post(f'/api/v1/shipments/{priced_shipment.token}/invoice')
    res2 = client.post(f'/api/v1/shipments/{priced_shipment.token}/invoice')
    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()['invoice_number'] == res2.json()['invoice_number']


def test_invoice_number_sequential(client, configured_db, shipment_type, db_session):
    """Each new shipment gets the next number in sequence."""
    def make_shipment(order_id: str) -> Shipment:
        s = Shipment(
            order_id=order_id,
            customer_name='Test',
            email='t@example.com',
            address='1 Rd',
            city='City',
            country='DE',
            zip='10000',
            shipment_type_id=shipment_type.id,
            weight_kg=Decimal('1.000'),
            amount_eur=Decimal('15.00'),
        )
        db_session.add(s)
        db_session.flush()
        return s

    s1 = make_shipment('ORD-SEQ-001')
    s2 = make_shipment('ORD-SEQ-002')

    r1 = client.post(f'/api/v1/shipments/{s1.token}/invoice')
    r2 = client.post(f'/api/v1/shipments/{s2.token}/invoice')

    n1 = r1.json()['invoice_number']
    n2 = r2.json()['invoice_number']
    # Extract sequence part and verify n2 is exactly one more than n1
    seq1 = int(n1.rsplit('-', 1)[-1])
    seq2 = int(n2.rsplit('-', 1)[-1])
    assert seq2 == seq1 + 1


def test_generate_invoice_shipment_not_found(client, configured_db):
    res = client.post('/api/v1/shipments/bad-token/invoice')
    assert res.status_code == 404


def test_generate_invoice_no_amount(client, db_session, shipment_type, configured_db):
    """Invoice cannot be generated before shipping cost is known."""
    s = Shipment(
        order_id='ORD-NO-AMOUNT',
        customer_name='Test',
        email='t@example.com',
        address='1 Rd',
        city='City',
        country='DE',
        zip='10000',
        shipment_type_id=shipment_type.id,
        weight_kg=Decimal('1.000'),
        amount_eur=None,
    )
    db_session.add(s)
    db_session.flush()
    res = client.post(f'/api/v1/shipments/{s.token}/invoice')
    assert res.status_code == 422


def test_generate_invoice_missing_config(client, priced_shipment, db_session):
    """Returns 503 when required config entries are absent."""
    # No config seeded — all values missing
    res = client.post(f'/api/v1/shipments/{priced_shipment.token}/invoice')
    assert res.status_code == 503


def test_generate_invoice_uses_custom_prefix(client, priced_shipment, db_session):
    db_session.add(Config(name='invoice_prefix',      value='SHIP'))
    db_session.add(Config(name='recipient_name',      value='Test Co'))
    db_session.add(Config(name='recipient_address',   value='1 Rd, City'))
    db_session.add(Config(name='recipient_iban',      value='DE00000000000000000000'))
    db_session.add(Config(name='recipient_bic',       value='TESTDE00'))
    db_session.flush()
    res = client.post(f'/api/v1/shipments/{priced_shipment.token}/invoice')
    assert res.status_code == 201
    assert res.json()['invoice_number'].startswith('SHIP-')


# ---------------------------------------------------------------------------
# GET /api/v1/shipments/{token}/invoice/pdf
# ---------------------------------------------------------------------------

def test_get_invoice_pdf(client, priced_shipment, configured_db):
    client.post(f'/api/v1/shipments/{priced_shipment.token}/invoice')
    res = client.get(f'/api/v1/shipments/{priced_shipment.token}/invoice/pdf')
    assert res.status_code == 200
    assert res.headers['content-type'] == 'application/pdf'
    assert res.content[:4] == b'%PDF'


def test_get_invoice_pdf_not_generated(client, priced_shipment):
    res = client.get(f'/api/v1/shipments/{priced_shipment.token}/invoice/pdf')
    assert res.status_code == 404


def test_get_invoice_pdf_shipment_not_found(client):
    res = client.get('/api/v1/shipments/ghost-token/invoice/pdf')
    assert res.status_code == 404
