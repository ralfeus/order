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

VALID_PAYLOAD_WITH_DIMS = {
    **VALID_PAYLOAD,
    'order_id': 'ORD-2026-04-0003',
    'length_cm': '40.0',
    'width_cm': '30.0',
    'height_cm': '20.0',
}


# ---------------------------------------------------------------------------
# POST /api/v1/shipments
# ---------------------------------------------------------------------------

def test_create_shipment_success(api_client, shipment_type, rate_data):
    response = api_client.post('/api/v1/shipments', json=VALID_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert 'id' in data
    assert 'token' in data
    assert 'shipment_url' in data
    assert data['token'] in data['shipment_url']


def test_create_shipment_unknown_subtype(api_client):
    payload = {**VALID_PAYLOAD, 'shipment_type_code': 'UNKNOWN'}
    response = api_client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 422


def test_create_shipment_duplicate_order_id(api_client, shipment):
    payload = {**VALID_PAYLOAD, 'order_id': shipment.order_id}
    response = api_client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 409


def test_create_shipment_invalid_email(api_client, shipment_type):
    payload = {**VALID_PAYLOAD, 'email': 'not-an-email'}
    response = api_client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 422


def test_create_shipment_no_rate(api_client, shipment_type):
    """Shipment creation fails when no rate covers the destination/weight."""
    response = api_client.post('/api/v1/shipments', json=VALID_PAYLOAD)
    assert response.status_code == 422


def test_create_shipment_missing_required_field(api_client, shipment_type, rate_data):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != 'customer_name'}
    response = api_client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 422


def test_create_shipment_with_dimensions_stored(api_client, shipment_type, rate_data, db_session):
    """Dimensions are stored and returned in the response."""
    # 40×30×20 cm → volumetric = 24000/5000 = 4.8 kg; actual = 2 kg → billable = 4.8 kg
    # Rate covers ≤5 kg at 4.00, so request should succeed
    response = api_client.post('/api/v1/shipments', json=VALID_PAYLOAD_WITH_DIMS)
    assert response.status_code == 201
    created_id = response.json()['id']

    from app.models.shipment import Shipment
    db_session.expire_all()
    s = db_session.query(Shipment).filter_by(id=created_id).first()
    assert s is not None
    assert float(s.length_cm) == 40.0
    assert float(s.width_cm) == 30.0
    assert float(s.height_cm) == 20.0


def test_create_shipment_volumetric_weight_drives_cost(api_client, shipment_type, db_session):
    """When volumetric weight > actual, cost is based on volumetric weight."""
    from decimal import Decimal
    from app.models.shipping_rate import ShippingFlatRate, ShippingRateEntry

    db_session.add(ShippingFlatRate(rate_per_kg=Decimal('10.00')))
    db_session.add(ShippingRateEntry(
        shipment_type_code='GLS', country='DE',
        max_weight_kg=Decimal('5.000'), cost=Decimal('5.00'),
    ))
    db_session.flush()

    # 40×30×20 → 4.8 kg volumetric; actual 1 kg → billable 4.8 kg
    # cost = 10 × 4.8 + 5.00 = 53.00
    payload = {**VALID_PAYLOAD_WITH_DIMS, 'order_id': 'ORD-VOL-TEST', 'weight_kg': '1.000'}
    response = api_client.post('/api/v1/shipments', json=payload)
    assert response.status_code == 201

    from app.models.shipment import Shipment
    db_session.expire_all()
    s = db_session.query(Shipment).filter_by(order_id='ORD-VOL-TEST').first()
    assert s is not None
    assert float(s.amount_eur) == pytest.approx(53.00)


def test_create_shipment_without_dimensions_still_works(api_client, shipment_type, rate_data):
    """Omitting dimensions keeps existing behaviour (actual weight used)."""
    response = api_client.post('/api/v1/shipments', json=VALID_PAYLOAD)
    assert response.status_code == 201


def test_create_shipment_unauthenticated(client, shipment_type, rate_data):
    """Requests without credentials must be rejected."""
    response = client.post('/api/v1/shipments', json=VALID_PAYLOAD)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/shipments
# ---------------------------------------------------------------------------

def test_list_shipments_empty(api_client):
    response = api_client.get('/api/v1/shipments')
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_shipments_returns_created(api_client, shipment):
    response = api_client.get('/api/v1/shipments')
    assert response.status_code == 200
    ids = [s['order_id'] for s in response.json()]
    assert shipment.order_id in ids


def test_list_shipments_unauthenticated(client):
    """Requests without credentials must be rejected."""
    response = client.get('/api/v1/shipments')
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/shipments/{token}
# ---------------------------------------------------------------------------

def test_get_shipment_by_token(client, shipment):
    response = client.get(f'/api/v1/shipments/{shipment.token}')
    assert response.status_code == 200
    data = response.json()
    assert data['order_id'] == shipment.order_id
    assert data['status'] == 'incoming'


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


# ---------------------------------------------------------------------------
# GET /api/v1/shipments/cost
# ---------------------------------------------------------------------------

def test_get_cost_success(api_client, shipment_type, rate_data):
    # 12.00 × 2 + 4.00 (≤5 kg tier) = 28.00
    response = api_client.get('/api/v1/shipments/cost', params={
        'country': 'DE',
        'weight_kg': '2.000',
        'shipment_type_code': 'GLS',
    })
    assert response.status_code == 200
    assert float(response.json()['cost_eur']) == pytest.approx(28.00)


def test_get_cost_with_dimensions_volumetric_wins(api_client, shipment_type, rate_data):
    # 40×30×20 cm → 4.8 kg volumetric; actual 1 kg → billable 4.8 kg
    # 12.00 × 4.8 + 4.00 = 61.60
    response = api_client.get('/api/v1/shipments/cost', params={
        'country': 'DE',
        'weight_kg': '1.000',
        'shipment_type_code': 'GLS',
        'length_cm': '40.0',
        'width_cm': '30.0',
        'height_cm': '20.0',
    })
    assert response.status_code == 200
    assert float(response.json()['cost_eur']) == pytest.approx(61.60)


def test_get_cost_without_dimensions_uses_actual_weight(api_client, shipment_type, rate_data):
    # Same as test_get_cost_success: no dims → actual weight used
    response = api_client.get('/api/v1/shipments/cost', params={
        'country': 'DE',
        'weight_kg': '2.000',
        'shipment_type_code': 'GLS',
    })
    assert response.status_code == 200
    data = response.json()
    assert 'cost_eur' in data


def test_get_cost_unknown_carrier(api_client):
    response = api_client.get('/api/v1/shipments/cost', params={
        'country': 'DE',
        'weight_kg': '2.000',
        'shipment_type_code': 'UNKNOWN',
    })
    assert response.status_code == 422


def test_get_cost_no_rate(api_client, shipment_type):
    # No rate_data fixture → no rate entries → 422
    response = api_client.get('/api/v1/shipments/cost', params={
        'country': 'DE',
        'weight_kg': '2.000',
        'shipment_type_code': 'GLS',
    })
    assert response.status_code == 422


def test_get_cost_unknown_country(api_client, shipment_type, rate_data):
    response = api_client.get('/api/v1/shipments/cost', params={
        'country': 'FR',
        'weight_kg': '2.000',
        'shipment_type_code': 'GLS',
    })
    assert response.status_code == 422


def test_get_cost_unauthenticated(client, shipment_type, rate_data):
    """Requests without credentials must be rejected."""
    response = client.get('/api/v1/shipments/cost', params={
        'country': 'DE',
        'weight_kg': '2.000',
        'shipment_type_code': 'GLS',
    })
    assert response.status_code == 401
