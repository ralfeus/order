"""Tests for GET /api/v1/shipments/{token}/tracking."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TRACK24_RESPONSE_WITH_EVENTS = {
    'data': [
        {
            'name': 'GLS',
            'checkpoints': [
                {'date': '2026-04-08 10:00', 'location': 'Seoul, KR', 'status': 'Parcel handed over to GLS'},
                {'date': '2026-04-07 08:30', 'location': 'Incheon, KR', 'status': 'In transit'},
            ],
        }
    ]
}

TRACK24_RESPONSE_EMPTY = {'data': []}

TRACK24_RESPONSE_NO_CHECKPOINTS = {
    'data': [{'name': 'GLS', 'checkpoints': []}]
}


def _mock_httpx(json_data: dict, status_code: int = 200):
    """Return a context-manager mock for httpx.AsyncClient that returns json_data."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()  # no-op for 200

    async_client = AsyncMock()
    async_client.get = AsyncMock(return_value=response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=async_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_tracking_returns_events(client, shipment):
    """Tracking code present → events from track24 are returned."""
    with patch('app.routes.tracking.httpx.AsyncClient', return_value=_mock_httpx(TRACK24_RESPONSE_WITH_EVENTS)):
        res = client.get(f'/api/v1/shipments/{shipment.token}/tracking')

    assert res.status_code == 200
    data = res.json()
    assert data['tracking_code'] == shipment.tracking_code
    assert data['carrier'] == 'GLS'
    assert len(data['events']) == 2
    assert data['events'][0]['location'] == 'Seoul, KR'
    assert data['events'][0]['description'] == 'Parcel handed over to GLS'


def test_tracking_empty_response(client, shipment):
    """track24 returns no data → events list is empty, no error."""
    with patch('app.routes.tracking.httpx.AsyncClient', return_value=_mock_httpx(TRACK24_RESPONSE_EMPTY)):
        res = client.get(f'/api/v1/shipments/{shipment.token}/tracking')

    assert res.status_code == 200
    data = res.json()
    assert data['events'] == []
    assert data['carrier'] is None


def test_tracking_no_checkpoints(client, shipment):
    """Carrier found but no checkpoints yet → empty events, carrier name set."""
    with patch('app.routes.tracking.httpx.AsyncClient', return_value=_mock_httpx(TRACK24_RESPONSE_NO_CHECKPOINTS)):
        res = client.get(f'/api/v1/shipments/{shipment.token}/tracking')

    assert res.status_code == 200
    data = res.json()
    assert data['events'] == []
    assert data['carrier'] == 'GLS'


def test_tracking_shipment_not_found(client):
    res = client.get('/api/v1/shipments/nonexistent-token/tracking')
    assert res.status_code == 404


def test_tracking_no_tracking_code(client, db_session, shipment_type):
    """Shipment without tracking_code returns 404."""
    from app.models.shipment import Shipment
    s = Shipment(
        order_id='ORD-NO-TRACK',
        customer_name='No Track',
        email='notrack@example.com',
        address='1 Road',
        city='City',
        country='DE',
        zip='10001',
        shipment_type_id=shipment_type.id,
        weight_kg='1.000',
        tracking_code=None,
    )
    db_session.add(s)
    db_session.flush()

    res = client.get(f'/api/v1/shipments/{s.token}/tracking')
    assert res.status_code == 404
    assert 'tracking' in res.json()['detail'].lower()


def test_tracking_upstream_timeout(client, shipment):
    """track24 times out → 504 returned to caller."""
    import httpx as _httpx

    async_client = AsyncMock()
    async_client.get = AsyncMock(side_effect=_httpx.TimeoutException('timeout'))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=async_client)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch('app.routes.tracking.httpx.AsyncClient', return_value=cm):
        res = client.get(f'/api/v1/shipments/{shipment.token}/tracking')

    assert res.status_code == 504


def test_tracking_upstream_http_error(client, shipment):
    """track24 returns 5xx → 502 returned to caller."""
    import httpx as _httpx

    mock_response = MagicMock()
    mock_response.status_code = 503
    http_error = _httpx.HTTPStatusError('error', request=MagicMock(), response=mock_response)

    async_client = AsyncMock()
    async_client.get = AsyncMock(side_effect=http_error)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=async_client)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch('app.routes.tracking.httpx.AsyncClient', return_value=cm):
        res = client.get(f'/api/v1/shipments/{shipment.token}/tracking')

    assert res.status_code == 502
