'''Tests for shipment CRUD endpoints'''
from decimal import Decimal

import pytest

from app.models.shipping_rate import ShippingFlatRate, ShippingRateEntry


@pytest.fixture
def rate_data(db_session):
    db_session.add(ShippingFlatRate(rate_per_kg=Decimal('12.00')))
    db_session.add(ShippingRateEntry(
        shipment_type_code='GLS', country='DE',
        max_weight_kg=Decimal('5.000'), cost=Decimal('4.00'),
    ))
    db_session.flush()


VALID_PAYLOAD = {
    'order_id': 'ORD-2026-04-0002',
    'customer_name': 'John Smith',
    'email': 'john@example.com',
    'address': '456 Side St',
    'city': 'Berlin',
    'country': 'DE',
    'zip': '10115',
    'phone': '+49123456789',
    'shipment_type_code': 'GLS',
    'weight_kg': '2.000',
    'tracking_code': 'TRACK456',
}


# ---------------------------------------------------------------------------
# POST /api/v1/shipments
# ---------------------------------------------------------------------------

def test_create_shipment_success(client, shipment_type, rate_data):
    response = client.post('/api/v1/shipments', json=VALID_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert 'id' in data
    assert 'token' in data
    assert 'shipment_url' in data
    assert data['token'] in data['shipment_url']


def test_create_shipment_unknown_subtype(client):
    payload = {**VALID_PAYLOAD, 'shipment_type_code': 'UNKNOWN'}
    response = client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 422


def test_create_shipment_duplicate_order_id(client, shipment):
    payload = {**VALID_PAYLOAD, 'order_id': shipment.order_id}
    response = client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 409


def test_create_shipment_invalid_email(client, shipment_type):
    payload = {**VALID_PAYLOAD, 'email': 'not-an-email'}
    response = client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 422


def test_create_shipment_no_rate(client, shipment_type):
    """Shipment creation fails when no rate covers the destination/weight."""
    response = client.post('/api/v1/shipments', json=VALID_PAYLOAD)
    assert response.status_code == 422


def test_create_shipment_missing_required_field(client, shipment_type, rate_data):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != 'customer_name'}
    response = client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/shipments
# ---------------------------------------------------------------------------

def test_list_shipments_empty(client):
    response = client.get('/api/v1/shipments')
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_shipments_returns_created(client, shipment):
    response = client.get('/api/v1/shipments')
    assert response.status_code == 200
    ids = [s['order_id'] for s in response.json()]
    assert shipment.order_id in ids


# ---------------------------------------------------------------------------
# GET /api/v1/shipments/{token}
# ---------------------------------------------------------------------------

def test_get_shipment_by_token(client, shipment):
    response = client.get(f'/api/v1/shipments/{shipment.token}')
    assert response.status_code == 200
    data = response.json()
    assert data['order_id'] == shipment.order_id
    assert data['status'] == 'pending'


def test_get_shipment_not_found(client):
    response = client.get('/api/v1/shipments/nonexistent-token')
    assert response.status_code == 404


def test_get_shipment_auto_creates_user(client, shipment, db_session):
    from app.models.user import User
    response = client.get(f'/api/v1/shipments/{shipment.token}?user=testuser')
    assert response.status_code == 200
    user = db_session.query(User).filter_by(username='testuser').first()
    assert user is not None


def test_get_shipment_reuses_existing_user(client, shipment, db_session):
    from app.models.user import User
    # First visit creates the user
    client.get(f'/api/v1/shipments/{shipment.token}?user=returning_user')
    # Second visit must not create a duplicate
    client.get(f'/api/v1/shipments/{shipment.token}?user=returning_user')
    count = db_session.query(User).filter_by(username='returning_user').count()
    assert count == 1


def test_get_shipment_no_user_param_ok(client, shipment):
    response = client.get(f'/api/v1/shipments/{shipment.token}')
    assert response.status_code == 200
