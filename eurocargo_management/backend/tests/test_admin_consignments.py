"""Tests for POST /api/v1/admin/shipments/{id}/consignment."""
from __future__ import annotations

import base64
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LABEL_B64 = base64.b64encode(b'%PDF-fake-label').decode()

_DHL_SUCCESS_RESPONSE = {
    'items': [
        {
            'shipmentNo': 'JD014600006270173750',
            'trackingNo': 'JD014600006270173750',
            'label': {'b64': _LABEL_B64},
        }
    ]
}

_DHL_CONFIG = {
    'dhl_sandbox': 'true',
    'dhl_app_id': 'test_app_id',
    'dhl_app_token': 'test_token',
    'dhl_billing_number': '33333333330101',
    'dhl_product_code': 'V01PAK',
    'shipper_name': 'EuroCargo GmbH',
    'shipper_street': 'Hauptstraße 1',
    'shipper_postal_code': '10115',
    'shipper_city': 'Berlin',
    'shipper_country': 'DE',
    'shipper_email': 'ship@example.com',
    'shipper_phone': '+4930123456789',
}


@pytest.fixture
def dhl_config(db_session):
    """Seed DHL config values into the test DB."""
    for name, value in _DHL_CONFIG.items():
        db_session.add(Config(name=name, value=value))
    db_session.flush()


@pytest.fixture
def dhl_shipment_type(db_session):
    """A DHL carrier instance."""
    from app.carriers.dhl import DHLCarrier
    carrier = DHLCarrier(code='DHL', name='DHL Parcel DE', enabled=True)
    db_session.add(carrier)
    db_session.flush()
    return carrier


@pytest.fixture
def dhl_shipment(db_session, dhl_shipment_type):
    """A shipment assigned to DHL carrier."""
    from app.models.shipment import Shipment
    s = Shipment(
        order_id='ORD-DHL-0001',
        customer_name='Hans Mueller',
        email='hans@example.de',
        address='Berliner Str. 10',
        city='Hamburg',
        country='DE',
        zip='20095',
        phone='+4940123456',
        shipment_type_id=dhl_shipment_type.id,
        weight_kg='3.000',
        tracking_code=None,
        status='incoming',
    )
    db_session.add(s)
    db_session.flush()
    return s


# ---------------------------------------------------------------------------
# POST /api/v1/admin/shipments/{id}/consignment
# ---------------------------------------------------------------------------

def _mock_dhl_post(status_code=201, body=None):
    body = body or _DHL_SUCCESS_RESPONSE
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = body
    mock_response.text = str(body)
    return mock_response


def test_create_consignment_success(admin_client, dhl_shipment, dhl_config):
    mock_resp = _mock_dhl_post()
    with patch('app.carriers.dhl.httpx.post', return_value=mock_resp):
        res = admin_client.post(
            f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
            json={},
        )
    assert res.status_code == 200
    data = res.json()
    assert data['tracking_code'] == 'JD014600006270173750'
    assert data['status'] == 'shipped'


def test_create_consignment_requires_admin(regular_client, dhl_shipment, dhl_config):
    res = regular_client.post(
        f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
        json={},
    )
    assert res.status_code == 403


def test_create_consignment_requires_auth(client, dhl_shipment):
    res = client.post(
        f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
        json={},
    )
    assert res.status_code == 401


def test_create_consignment_not_found(admin_client):
    res = admin_client.post(
        '/api/v1/admin/shipments/99999/consignment',
        json={},
    )
    assert res.status_code == 404


def test_create_consignment_conflict_when_already_shipped(admin_client, dhl_shipment, dhl_config, db_session):
    """Returns 409 if status is already 'shipped' and force=False."""
    dhl_shipment.status = 'shipped'
    db_session.flush()

    res = admin_client.post(
        f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
        json={'force': False},
    )
    assert res.status_code == 409
    assert 'force' in res.json()['detail'].lower()


def test_create_consignment_conflict_when_tracking_exists(admin_client, dhl_shipment, dhl_config, db_session):
    """Returns 409 if tracking_code is already set and force=False."""
    dhl_shipment.tracking_code = 'EXISTING-TRACK'
    db_session.flush()

    res = admin_client.post(
        f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
        json={},
    )
    assert res.status_code == 409
    assert 'EXISTING-TRACK' in res.json()['detail']


def test_create_consignment_force_overwrites_existing_tracking(admin_client, dhl_shipment, dhl_config, db_session):
    """force=True bypasses the 409 guard."""
    dhl_shipment.tracking_code = 'OLD-TRACK'
    db_session.flush()

    mock_resp = _mock_dhl_post()
    with patch('app.carriers.dhl.httpx.post', return_value=mock_resp):
        res = admin_client.post(
            f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
            json={'force': True},
        )
    assert res.status_code == 200
    assert res.json()['tracking_code'] == 'JD014600006270173750'


def test_create_consignment_gls_carrier_returns_501(admin_client, shipment):
    """GLS carrier raises NotImplementedError → 501.

    The conftest 'shipment' fixture has tracking_code pre-set, so we pass
    force=True to bypass the 409 guard and reach the carrier method.
    """
    res = admin_client.post(
        f'/api/v1/admin/shipments/{shipment.id}/consignment',
        json={'force': True},
    )
    assert res.status_code == 501
    assert 'GLS' in res.json()['detail']


def test_create_consignment_missing_config_returns_422(admin_client, dhl_shipment):
    """Missing DHL config → 422 (no Config rows seeded)."""
    res = admin_client.post(
        f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
        json={},
    )
    assert res.status_code == 422
    assert 'Missing DHL configuration' in res.json()['detail']


def test_create_consignment_dhl_api_error_returns_502(admin_client, dhl_shipment, dhl_config):
    """DHL API HTTP error → 502."""
    mock_resp = _mock_dhl_post(status_code=500, body={'title': 'Internal Server Error'})
    with patch('app.carriers.dhl.httpx.post', return_value=mock_resp):
        res = admin_client.post(
            f'/api/v1/admin/shipments/{dhl_shipment.id}/consignment',
            json={},
        )
    assert res.status_code == 502


# ---------------------------------------------------------------------------
# Auto-trigger when status → shipped
# ---------------------------------------------------------------------------

def test_status_shipped_auto_creates_dhl_consignment(admin_client, dhl_shipment, dhl_config):
    """Setting status to 'shipped' auto-triggers DHL consignment creation."""
    mock_resp = _mock_dhl_post()
    with patch('app.carriers.dhl.httpx.post', return_value=mock_resp):
        res = admin_client.patch(
            f'/api/v1/admin/shipments/{dhl_shipment.id}/status',
            json={'status': 'shipped'},
        )
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'shipped'
    assert data['tracking_code'] == 'JD014600006270173750'


def test_status_shipped_auto_consignment_failure_does_not_prevent_status_update(
    admin_client, dhl_shipment, dhl_config
):
    """If auto-consignment fails, status is still updated (graceful degradation)."""
    import httpx as _httpx
    with patch('app.carriers.dhl.httpx.post', side_effect=_httpx.TimeoutException('timeout')):
        res = admin_client.patch(
            f'/api/v1/admin/shipments/{dhl_shipment.id}/status',
            json={'status': 'shipped'},
        )
    # Status update succeeds even though DHL call failed
    assert res.status_code == 200
    assert res.json()['status'] == 'shipped'


def test_status_shipped_gls_no_auto_consignment_still_updates(admin_client, shipment):
    """GLS: auto-consignment raises NotImplementedError — status update succeeds."""
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/status',
        json={'status': 'shipped'},
    )
    assert res.status_code == 200
    assert res.json()['status'] == 'shipped'


def test_status_already_shipped_no_duplicate_consignment(admin_client, dhl_shipment, dhl_config, db_session):
    """Transitioning shipped→shipped does NOT call create_consignment again."""
    dhl_shipment.status = 'shipped'
    dhl_shipment.tracking_code = 'EXISTING'
    db_session.flush()

    with patch('app.carriers.dhl.httpx.post') as mock_post:
        res = admin_client.patch(
            f'/api/v1/admin/shipments/{dhl_shipment.id}/status',
            json={'status': 'shipped'},
        )
    assert res.status_code == 200
    mock_post.assert_not_called()
