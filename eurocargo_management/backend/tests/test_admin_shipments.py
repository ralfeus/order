"""Tests for admin shipment endpoints (status + tracking)."""

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
        json={'status': 'at_warehouse'},
    )
    assert res.status_code == 200
    assert res.json()['status'] == 'at_warehouse'


def test_admin_update_status_all_values(admin_client, shipment):
    for status in ('incoming', 'at_warehouse', 'customs_cleared', 'shipped'):
        res = admin_client.patch(
            f'/api/v1/admin/shipments/{shipment.id}/status',
            json={'status': status},
        )
        assert res.status_code == 200, f'Expected 200 for status={status}'
        assert res.json()['status'] == status


def test_admin_update_status_invalid_value(admin_client, shipment):
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/status',
        json={'status': 'paid'},          # old value — now invalid
    )
    assert res.status_code == 422


def test_admin_update_status_not_found(admin_client):
    res = admin_client.patch('/api/v1/admin/shipments/99999/status', json={'status': 'shipped'})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/shipments/{id}/paid
# ---------------------------------------------------------------------------

def test_admin_set_paid_true(admin_client, shipment):
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/paid',
        json={'paid': True},
    )
    assert res.status_code == 200
    assert res.json()['paid'] is True


def test_admin_set_paid_false(admin_client, shipment):
    """Admin can un-pay a shipment."""
    # First mark as paid
    admin_client.patch(f'/api/v1/admin/shipments/{shipment.id}/paid', json={'paid': True})
    # Then revert
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/paid',
        json={'paid': False},
    )
    assert res.status_code == 200
    assert res.json()['paid'] is False


def test_admin_update_paid_not_found(admin_client):
    res = admin_client.patch('/api/v1/admin/shipments/99999/paid', json={'paid': True})
    assert res.status_code == 404


def test_admin_update_paid_requires_admin(regular_client, shipment):
    res = regular_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/paid',
        json={'paid': True},
    )
    assert res.status_code == 403


def test_admin_update_paid_requires_auth(client, shipment):
    res = client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/paid',
        json={'paid': True},
    )
    assert res.status_code == 401


def test_paid_independent_of_status(admin_client, shipment):
    """Paid flag and status are independent — both can be set freely."""
    admin_client.patch(f'/api/v1/admin/shipments/{shipment.id}/paid', json={'paid': True})
    res = admin_client.patch(
        f'/api/v1/admin/shipments/{shipment.id}/status',
        json={'status': 'at_warehouse'},
    )
    data = res.json()
    assert data['status'] == 'at_warehouse'
    assert data['paid'] is True


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
