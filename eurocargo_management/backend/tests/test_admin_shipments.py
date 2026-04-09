"""Tests for admin shipment endpoints (status + tracking)."""
import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user(db_session):
    user = User(
        username='admin_test',
        password_hash=hash_password('secret'),
        role='admin',
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_client(client, admin_user):
    """TestClient with admin Authorization header pre-set."""
    token = create_access_token(subject=admin_user.username, role=admin_user.role)
    client.headers.update({'Authorization': f'Bearer {token}'})
    return client


@pytest.fixture
def regular_user(db_session):
    user = User(username='regular_test', role=None)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def regular_client(client, regular_user):
    token = create_access_token(subject=regular_user.username, role=regular_user.role)
    client.headers.update({'Authorization': f'Bearer {token}'})
    return client


# ---------------------------------------------------------------------------
# GET /api/v1/admin/shipments
# ---------------------------------------------------------------------------

def test_admin_list_shipments(admin_client, shipment):
    res = admin_client.get('/api/v1/admin/shipments')
    assert res.status_code == 200
    ids = [s['order_id'] for s in res.json()]
    assert shipment.order_id in ids


def test_admin_list_requires_auth(client):
    res = client.get('/api/v1/admin/shipments')
    assert res.status_code == 401


def test_admin_list_requires_admin_role(regular_client, shipment):
    res = regular_client.get('/api/v1/admin/shipments')
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/shipments/{id}/status
# ---------------------------------------------------------------------------

def test_admin_update_status(admin_client, shipment):
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/status',
        json={'status': 'paid'},
    )
    assert res.status_code == 200
    assert res.json()['status'] == 'paid'


def test_admin_update_status_invalid_value(admin_client, shipment):
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/status',
        json={'status': 'lost'},
    )
    assert res.status_code == 422


def test_admin_update_status_not_found(admin_client):
    res = admin_client.patch('/api/v1/admin/shipments/99999/status', json={'status': 'paid'})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/shipments/{id}/tracking
# ---------------------------------------------------------------------------

def test_admin_update_tracking_set(admin_client, shipment):
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/tracking',
        json={'tracking_code': 'GLS-987654'},
    )
    assert res.status_code == 200
    assert res.json()['tracking_code'] == 'GLS-987654'


def test_admin_update_tracking_clear(admin_client, shipment):
    """Setting tracking_code to null clears it."""
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/tracking',
        json={'tracking_code': None},
    )
    assert res.status_code == 200
    assert res.json()['tracking_code'] is None


def test_admin_update_tracking_overwrite(admin_client, shipment):
    """Tracking code can be updated multiple times."""
    admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/tracking',
        json={'tracking_code': 'FIRST'},
    )
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/tracking',
        json={'tracking_code': 'SECOND'},
    )
    assert res.status_code == 200
    assert res.json()['tracking_code'] == 'SECOND'


def test_admin_update_tracking_not_found(admin_client):
    res = admin_client.patch(
        '/api/v1/admin/shipments/99999/tracking',
        json={'tracking_code': 'NOPE'},
    )
    assert res.status_code == 404


def test_admin_update_tracking_requires_admin(regular_client, shipment):
    res = regular_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/tracking',
        json={'tracking_code': 'HACK'},
    )
    assert res.status_code == 403


def test_admin_update_tracking_requires_auth(client, shipment):
    res = client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/tracking',
        json={'tracking_code': 'HACK'},
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Auth — login endpoint
# ---------------------------------------------------------------------------

def test_login_success(client, admin_user):
    res = client.post('/api/v1/admin/auth/login',
                      json={'username': 'admin_test', 'password': 'secret'})
    assert res.status_code == 200
    data = res.json()
    assert 'access_token' in data
    assert data['token_type'] == 'bearer'


def test_login_wrong_password(client, admin_user):
    res = client.post('/api/v1/admin/auth/login',
                      json={'username': 'admin_test', 'password': 'wrong'})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post('/api/v1/admin/auth/login',
                      json={'username': 'nobody', 'password': 'x'})
    assert res.status_code == 401
