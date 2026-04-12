"""Tests for shipment attachment endpoints."""
from io import BytesIO

import pytest

from app.models.shipment_attachment import MAX_SIZE_BYTES


def _upload(client, shipment, content=b'%PDF fake', content_type='application/pdf',
            filename='doc.pdf'):
    return client.post(
        f'/api/v1/shipments/{shipment.token}/attachments',
        files={'file': (filename, BytesIO(content), content_type)},
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def test_upload_pdf(client, shipment):
    res = _upload(client, shipment)
    assert res.status_code == 201
    data = res.json()
    assert data['filename'] == 'doc.pdf'
    assert data['content_type'] == 'application/pdf'
    assert data['size_bytes'] == len(b'%PDF fake')
    assert 'id' in data
    assert 'uploaded_at' in data


def test_upload_jpeg(client, shipment):
    res = _upload(client, shipment, content=b'\xff\xd8\xff',
                  content_type='image/jpeg', filename='photo.jpg')
    assert res.status_code == 201


def test_upload_png(client, shipment):
    res = _upload(client, shipment, content=b'\x89PNG',
                  content_type='image/png', filename='scan.png')
    assert res.status_code == 201


def test_upload_multiple_files(client, shipment):
    _upload(client, shipment, filename='a.pdf')
    _upload(client, shipment, filename='b.pdf')
    res = client.get(f'/api/v1/shipments/{shipment.token}/attachments')
    assert len(res.json()) == 2


def test_upload_wrong_mime_rejected(client, shipment):
    res = _upload(client, shipment, content_type='text/plain', filename='note.txt')
    assert res.status_code == 422
    assert 'Unsupported file type' in res.json()['detail']


def test_upload_too_large_rejected(client, shipment):
    res = _upload(client, shipment, content=b'x' * (MAX_SIZE_BYTES + 1))
    assert res.status_code == 422
    assert 'too large' in res.json()['detail']


def test_upload_unknown_shipment(client):
    res = client.post(
        '/api/v1/shipments/bad-token/attachments',
        files={'file': ('f.pdf', BytesIO(b'%PDF'), 'application/pdf')},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_empty(client, shipment):
    res = client.get(f'/api/v1/shipments/{shipment.token}/attachments')
    assert res.status_code == 200
    assert res.json() == []


def test_list_excludes_binary(client, shipment):
    _upload(client, shipment)
    res = client.get(f'/api/v1/shipments/{shipment.token}/attachments')
    assert res.status_code == 200
    item = res.json()[0]
    assert 'data' not in item
    assert 'filename' in item
    assert 'size_bytes' in item


def test_list_unknown_shipment(client):
    res = client.get('/api/v1/shipments/bad-token/attachments')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def test_download(client, shipment):
    _upload(client, shipment, content=b'%PDF content', filename='proof.pdf')
    attachment_id = client.get(
        f'/api/v1/shipments/{shipment.token}/attachments'
    ).json()[0]['id']

    res = client.get(f'/api/v1/shipments/{shipment.token}/attachments/{attachment_id}')
    assert res.status_code == 200
    assert res.content == b'%PDF content'
    assert res.headers['content-type'] == 'application/pdf'
    assert res.headers['content-disposition'].startswith('inline')
    assert 'proof.pdf' in res.headers['content-disposition']


def test_download_not_found(client, shipment):
    res = client.get(f'/api/v1/shipments/{shipment.token}/attachments/99999')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete(client, shipment):
    _upload(client, shipment, filename='to_delete.pdf')
    attachment_id = client.get(
        f'/api/v1/shipments/{shipment.token}/attachments'
    ).json()[0]['id']

    res = client.delete(f'/api/v1/shipments/{shipment.token}/attachments/{attachment_id}')
    assert res.status_code == 204

    res = client.get(f'/api/v1/shipments/{shipment.token}/attachments')
    assert res.json() == []


def test_delete_not_found(client, shipment):
    res = client.delete(f'/api/v1/shipments/{shipment.token}/attachments/99999')
    assert res.status_code == 404


def test_delete_only_own_shipments_attachment(client, shipment, db_session, shipment_type):
    """Cannot delete an attachment that belongs to a different shipment."""
    from app.models.shipment import Shipment as ShipmentModel
    other = ShipmentModel(
        order_id='ORD-OTHER-001',
        customer_name='Other', email='other@example.com',
        address='1 St', city='City', country='DE', zip='10000',
        shipment_type_id=shipment_type.id, weight_kg='1.000',
    )
    db_session.add(other)
    db_session.flush()

    _upload(client, other, filename='other.pdf')
    attachment_id = client.get(
        f'/api/v1/shipments/{other.token}/attachments'
    ).json()[0]['id']

    res = client.delete(
        f'/api/v1/shipments/{shipment.token}/attachments/{attachment_id}'
    )
    assert res.status_code == 404
