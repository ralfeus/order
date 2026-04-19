"""Tests for audit logging of shipment modifications (stdout via logging)."""
import io
import logging

import pytest
from unittest.mock import patch

from app.carriers.gls import GLSCarrier
from app.models.shipment_attachment import ShipmentAttachment


# ─── status_changed ──────────────────────────────────────────────────────────

def test_log_status_change(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch(
            f'/api/v1/admin/shipments/{shipment.id}/status',
            json={'status': 'at_warehouse'},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    msg = audit[0].message
    assert shipment.order_id in msg
    assert 'user=admin_test' in msg
    assert 'action=status_changed' in msg
    assert 'old=incoming' in msg
    assert 'new=at_warehouse' in msg


def test_log_status_change_no_audit_on_404(admin_client, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch('/api/v1/admin/shipments/99999/status', json={'status': 'shipped'})
    assert not any('AUDIT' in r.message for r in caplog.records)


# ─── paid_changed ────────────────────────────────────────────────────────────

def test_log_paid_toggle_true(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch(
            f'/api/v1/admin/shipments/{shipment.id}/paid',
            json={'paid': True},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    msg = audit[0].message
    assert shipment.order_id in msg
    assert 'user=admin_test' in msg
    assert 'action=paid_changed' in msg
    assert 'new=True' in msg


def test_log_paid_toggle_false(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch(
            f'/api/v1/admin/shipments/{shipment.id}/paid',
            json={'paid': False},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    assert 'new=False' in audit[0].message


def test_log_paid_no_audit_on_404(admin_client, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch('/api/v1/admin/shipments/99999/paid', json={'paid': True})
    assert not any('AUDIT' in r.message for r in caplog.records)


# ─── tracking_changed ────────────────────────────────────────────────────────

def test_log_tracking_change(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch(
            f'/api/v1/admin/shipments/{shipment.id}/tracking',
            json={'tracking_code': 'NEWTRACK999'},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    msg = audit[0].message
    assert shipment.order_id in msg
    assert 'user=admin_test' in msg
    assert 'action=tracking_changed' in msg
    assert 'new=NEWTRACK999' in msg


def test_log_tracking_clear(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch(
            f'/api/v1/admin/shipments/{shipment.id}/tracking',
            json={'tracking_code': None},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    assert 'new=None' in audit[0].message


def test_log_tracking_no_audit_on_404(admin_client, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.shipments'):
        admin_client.patch('/api/v1/admin/shipments/99999/tracking', json={'tracking_code': 'X'})
    assert not any('AUDIT' in r.message for r in caplog.records)


# ─── consignment_created ─────────────────────────────────────────────────────

def test_log_consignment_created(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.consignments'):
        with patch.object(GLSCarrier, 'create_consignment', return_value=None):
            admin_client.post(
                f'/api/v1/admin/shipments/{shipment.id}/consignment',
                json={'force': True},
            )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    msg = audit[0].message
    assert shipment.order_id in msg
    assert 'user=admin_test' in msg
    assert 'action=consignment_created' in msg


def test_log_consignment_no_audit_on_404(admin_client, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.admin.consignments'):
        admin_client.post('/api/v1/admin/shipments/99999/consignment', json={'force': True})
    assert not any('AUDIT' in r.message for r in caplog.records)


# ─── attachment_added ────────────────────────────────────────────────────────

def test_log_attachment_added(admin_client, shipment, caplog):
    with caplog.at_level(logging.INFO, logger='app.routes.attachments'):
        admin_client.post(
            f'/api/v1/shipments/{shipment.token}/attachments',
            files={'file': ('receipt.pdf', io.BytesIO(b'%PDF-1.4 fake'), 'application/pdf')},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    msg = audit[0].message
    assert shipment.order_id in msg
    assert 'user=admin_test' in msg
    assert 'action=attachment_added' in msg
    assert 'receipt.pdf' in msg


def test_log_attachment_added_username_from_jwt(admin_client, shipment, caplog):
    """Username in the log must come from the JWT sub, not be hardcoded."""
    with caplog.at_level(logging.INFO, logger='app.routes.attachments'):
        admin_client.post(
            f'/api/v1/shipments/{shipment.token}/attachments',
            files={'file': ('doc.pdf', io.BytesIO(b'%PDF-1.4'), 'application/pdf')},
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert any('user=admin_test' in r.message for r in audit)


# ─── attachment_removed ──────────────────────────────────────────────────────

def test_log_attachment_removed(admin_client, shipment, db_session, caplog):
    attachment = ShipmentAttachment(
        shipment_id=shipment.id,
        filename='to_delete.pdf',
        content_type='application/pdf',
        size_bytes=5,
        data=b'hello',
    )
    db_session.add(attachment)
    db_session.flush()

    with caplog.at_level(logging.INFO, logger='app.routes.attachments'):
        admin_client.delete(
            f'/api/v1/shipments/{shipment.token}/attachments/{attachment.id}',
        )
    audit = [r for r in caplog.records if 'AUDIT' in r.message]
    assert len(audit) == 1
    msg = audit[0].message
    assert shipment.order_id in msg
    assert 'user=admin_test' in msg
    assert 'action=attachment_removed' in msg
    assert 'to_delete.pdf' in msg
