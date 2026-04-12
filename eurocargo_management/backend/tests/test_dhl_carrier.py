"""Tests for DHLCarrier.create_consignment() using mocked httpx."""
from __future__ import annotations

import base64
import json
import types
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.carriers.dhl import DHLCarrier
from app.models.config import Config
from app.models.shipment import Shipment
from app.models.shipment_attachment import ShipmentAttachment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_carrier():
    """Create a DHLCarrier-like object without SQLAlchemy instrumentation.

    We use a SimpleNamespace and bind the real DHLCarrier methods to it so
    that unit tests for pure logic (config loading, payload building, etc.)
    don't require a database session.
    """
    obj = types.SimpleNamespace()
    obj.id = 1
    obj.code = 'DHL'
    for method_name in (
        '_load_config', '_base_url', '_auth_header',
        '_build_payload', '_call_dhl_api', 'create_consignment',
    ):
        bound = getattr(DHLCarrier, method_name).__get__(obj, type(obj))
        setattr(obj, method_name, bound)
    return obj


def _make_shipment(**kwargs):
    defaults = dict(
        id=1,
        order_id='ORD-2026-04-0001',
        customer_name='Jane Doe',
        email='jane@example.com',
        address='123 Main St',
        city='Prague',
        country='CZ',
        zip='11000',
        phone='+420123456789',
        weight_kg=Decimal('2.000'),
        tracking_code=None,
        status='incoming',
    )
    defaults.update(kwargs)
    shipment = MagicMock(spec=Shipment)
    for k, v in defaults.items():
        setattr(shipment, k, v)
    return shipment


def _make_db(config_entries: dict) -> MagicMock:
    db = MagicMock()
    rows = []
    for k, v in config_entries.items():
        row = MagicMock(spec=['name', 'value'])
        row.name = k
        row.value = v
        rows.append(row)
    db.query.return_value.all.return_value = rows
    return db


_FULL_CONFIG = {
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


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------

def test_load_config_all_present():
    carrier = _make_carrier()
    db = _make_db(_FULL_CONFIG)
    cfg = carrier._load_config(db)
    assert cfg['dhl_app_id'] == 'test_app_id'
    assert cfg['shipper_name'] == 'EuroCargo GmbH'


def test_load_config_missing_required_raises():
    carrier = _make_carrier()
    incomplete = {k: v for k, v in _FULL_CONFIG.items() if k != 'dhl_billing_number'}
    db = _make_db(incomplete)
    with pytest.raises(ValueError, match='dhl_billing_number'):
        carrier._load_config(db)


def test_load_config_multiple_missing_listed():
    carrier = _make_carrier()
    minimal = {'dhl_sandbox': 'true'}
    db = _make_db(minimal)
    with pytest.raises(ValueError) as exc_info:
        carrier._load_config(db)
    msg = str(exc_info.value)
    assert 'dhl_app_id' in msg
    assert 'shipper_name' in msg


# ---------------------------------------------------------------------------
# _base_url
# ---------------------------------------------------------------------------

def test_base_url_sandbox():
    carrier = _make_carrier()
    cfg = {'dhl_sandbox': 'true'}
    assert 'sandbox' in carrier._base_url(cfg)


def test_base_url_production():
    carrier = _make_carrier()
    cfg = {'dhl_sandbox': 'false'}
    assert 'sandbox' not in carrier._base_url(cfg)


def test_base_url_defaults_to_sandbox():
    """Missing dhl_sandbox key defaults to sandbox."""
    carrier = _make_carrier()
    assert 'sandbox' in carrier._base_url({})


# ---------------------------------------------------------------------------
# _auth_header
# ---------------------------------------------------------------------------

def test_auth_header_is_basic():
    carrier = _make_carrier()
    cfg = {'dhl_app_id': 'myid', 'dhl_app_token': 'mytoken'}
    header = carrier._auth_header(cfg)
    assert header.startswith('Basic ')
    decoded = base64.b64decode(header[6:]).decode()
    assert decoded == 'myid:mytoken'


# ---------------------------------------------------------------------------
# _build_payload
# ---------------------------------------------------------------------------

def test_build_payload_shipper_from_config():
    carrier = _make_carrier()
    shipment = _make_shipment()
    payload = carrier._build_payload(shipment, _FULL_CONFIG)
    shipper = payload['shipments'][0]['shipper']
    assert shipper['name1'] == 'EuroCargo GmbH'
    assert shipper['postalCode'] == '10115'
    assert shipper['country'] == 'DE'


def test_build_payload_consignee_from_shipment():
    carrier = _make_carrier()
    shipment = _make_shipment(customer_name='Max Mustermann', city='Berlin', country='DE')
    payload = carrier._build_payload(shipment, _FULL_CONFIG)
    consignee = payload['shipments'][0]['consignee']
    assert consignee['name1'] == 'Max Mustermann'
    assert consignee['city'] == 'Berlin'
    assert consignee['country'] == 'DE'


def test_build_payload_weight():
    carrier = _make_carrier()
    shipment = _make_shipment(weight_kg=Decimal('3.500'))
    payload = carrier._build_payload(shipment, _FULL_CONFIG)
    weight = payload['shipments'][0]['details']['weight']
    assert weight['uom'] == 'kg'
    assert weight['value'] == pytest.approx(3.5)


def test_build_payload_ref_no_is_order_id():
    carrier = _make_carrier()
    shipment = _make_shipment(order_id='ORD-TEST-001')
    payload = carrier._build_payload(shipment, _FULL_CONFIG)
    assert payload['shipments'][0]['refNo'] == 'ORD-TEST-001'


# ---------------------------------------------------------------------------
# create_consignment — success path
# ---------------------------------------------------------------------------

def test_create_consignment_sets_tracking_and_status():
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = _DHL_SUCCESS_RESPONSE

    with patch('app.carriers.dhl.httpx.post', return_value=mock_response):
        carrier.create_consignment(shipment, db)

    assert shipment.tracking_code == 'JD014600006270173750'
    assert shipment.status == 'shipped'


def test_create_consignment_stores_label_attachment():
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = _DHL_SUCCESS_RESPONSE

    added_objects = []
    db.add.side_effect = added_objects.append

    with patch('app.carriers.dhl.httpx.post', return_value=mock_response):
        carrier.create_consignment(shipment, db)

    attachments = [o for o in added_objects if isinstance(o, ShipmentAttachment)]
    assert len(attachments) == 1
    att = attachments[0]
    assert att.filename == 'JD014600006270173750.pdf'
    assert att.content_type == 'application/pdf'
    assert att.data == b'%PDF-fake-label'


def test_create_consignment_no_label_does_not_add_attachment():
    """If DHL returns no label, no attachment is stored but tracking is set."""
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    response_no_label = {
        'items': [{'shipmentNo': 'TRACK001', 'label': {}}]
    }
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = response_no_label

    added_objects = []
    db.add.side_effect = added_objects.append

    with patch('app.carriers.dhl.httpx.post', return_value=mock_response):
        carrier.create_consignment(shipment, db)

    attachments = [o for o in added_objects if isinstance(o, ShipmentAttachment)]
    assert len(attachments) == 0
    assert shipment.tracking_code == 'TRACK001'


# ---------------------------------------------------------------------------
# create_consignment — error paths
# ---------------------------------------------------------------------------

def test_create_consignment_timeout_raises_runtime_error():
    import httpx as _httpx
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    with patch('app.carriers.dhl.httpx.post', side_effect=_httpx.TimeoutException('timeout')):
        with pytest.raises(RuntimeError, match='timed out'):
            carrier.create_consignment(shipment, db)


def test_create_consignment_connection_error_raises_runtime_error():
    import httpx as _httpx
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    with patch('app.carriers.dhl.httpx.post', side_effect=_httpx.ConnectError('refused')):
        with pytest.raises(RuntimeError, match='connection error'):
            carrier.create_consignment(shipment, db)


def test_create_consignment_non_2xx_raises_runtime_error():
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"title": "Bad request"}'

    with patch('app.carriers.dhl.httpx.post', return_value=mock_response):
        with pytest.raises(RuntimeError, match='400'):
            carrier.create_consignment(shipment, db)


def test_create_consignment_no_items_raises_runtime_error():
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db(_FULL_CONFIG)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'items': []}

    with patch('app.carriers.dhl.httpx.post', return_value=mock_response):
        with pytest.raises(RuntimeError, match='no shipment items'):
            carrier.create_consignment(shipment, db)


def test_create_consignment_missing_config_raises_value_error():
    carrier = _make_carrier()
    shipment = _make_shipment()
    db = _make_db({'dhl_sandbox': 'true'})  # missing required keys

    with pytest.raises(ValueError, match='Missing DHL configuration'):
        carrier.create_consignment(shipment, db)
