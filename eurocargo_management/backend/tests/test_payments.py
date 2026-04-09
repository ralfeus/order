'''Tests for POST /api/v1/shipments/{token}/payments and Revolut webhook'''
from unittest.mock import MagicMock, patch
from decimal import Decimal

import pytest

from app.models.shipment import Shipment


@pytest.fixture
def priced_shipment(db_session, shipment_type):
    """Shipment with amount_eur already calculated — required for payment tests."""
    s = Shipment(
        order_id='ORD-2026-04-9999',
        customer_name='Pay Test',
        email='pay@example.com',
        address='1 Pay St',
        city='Vienna',
        country='AT',
        zip='1010',
        shipment_type_id=shipment_type.id,
        weight_kg=Decimal('2.000'),
        amount_eur=Decimal('25.00'),
    )
    db_session.add(s)
    db_session.flush()
    return s


# ---------------------------------------------------------------------------
# POST /api/v1/shipments/{token}/payments
# ---------------------------------------------------------------------------

MOCK_REVOLUT_RESPONSE = {
    'id': 'rev-order-abc123',
    'checkout_url': 'https://sandbox.revolut.com/checkout/abc123',
}


def test_create_payment_success(client, priced_shipment):
    with patch('app.routes.revolut.revolut_client.create_order',
               return_value=MOCK_REVOLUT_RESPONSE):
        response = client.post(
            f'/api/v1/shipments/{priced_shipment.token}/payments',
            json={'method': 'card'},
        )
    assert response.status_code == 201
    data = response.json()
    assert data['revolut_order_id'] == 'rev-order-abc123'
    assert data['checkout_url'] == MOCK_REVOLUT_RESPONSE['checkout_url']
    assert data['status'] == 'pending'
    assert data['method'] == 'card'


def test_create_payment_sepa(client, priced_shipment):
    with patch('app.routes.revolut.revolut_client.create_order',
               return_value=MOCK_REVOLUT_RESPONSE):
        response = client.post(
            f'/api/v1/shipments/{priced_shipment.token}/payments',
            json={'method': 'sepa'},
        )
    assert response.status_code == 201
    assert response.json()['method'] == 'sepa'


def test_create_payment_invalid_method(client, priced_shipment):
    response = client.post(
        f'/api/v1/shipments/{priced_shipment.token}/payments',
        json={'method': 'bitcoin'},
    )
    assert response.status_code == 422


def test_create_payment_no_amount(client, shipment):
    """Payment cannot be initiated before shipping cost is calculated."""
    response = client.post(
        f'/api/v1/shipments/{shipment.token}/payments',
        json={'method': 'card'},
    )
    assert response.status_code == 422


def test_create_payment_shipment_not_found(client):
    response = client.post('/api/v1/shipments/bad-token/payments', json={'method': 'card'})
    assert response.status_code == 404


def test_create_payment_already_paid(client, priced_shipment, db_session):
    priced_shipment.status = 'paid'
    db_session.flush()
    response = client.post(
        f'/api/v1/shipments/{priced_shipment.token}/payments',
        json={'method': 'card'},
    )
    assert response.status_code == 409


def test_create_payment_revolut_error(client, priced_shipment):
    with patch('app.routes.revolut.revolut_client.create_order',
               side_effect=Exception('Revolut is down')):
        response = client.post(
            f'/api/v1/shipments/{priced_shipment.token}/payments',
            json={'method': 'card'},
        )
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# POST /api/v1/revolut/webhooks
# ---------------------------------------------------------------------------

def test_webhook_order_completed(client, priced_shipment, db_session):
    from app.models.payment import Payment
    shipment = priced_shipment

    # Pre-create a pending payment with a known revolut_order_id
    payment = Payment(
        shipment_id=shipment.id,
        revolut_order_id='rev-webhook-test',
        method='card',
        status='pending',
        amount_eur=shipment.amount_eur,
        checkout_url='https://checkout.example.com',
    )
    db_session.add(payment)
    db_session.flush()

    with patch('app.routes.revolut.revolut_client.verify_webhook', return_value=True):
        response = client.post(
            '/api/v1/revolut/webhooks',
            json={'event': 'ORDER_COMPLETED', 'order_id': 'rev-webhook-test'},
            headers={'revolut-signature': 'dummy'},
        )
    assert response.status_code == 200

    db_session.refresh(payment)
    db_session.refresh(shipment)
    assert payment.status == 'paid'
    assert shipment.status == 'paid'


def test_webhook_invalid_signature(client, shipment):
    with patch('app.routes.revolut.revolut_client.verify_webhook', return_value=False):
        response = client.post(
            '/api/v1/revolut/webhooks',
            json={'event': 'ORDER_COMPLETED', 'order_id': 'anything'},
            headers={'revolut-signature': 'bad-sig'},
        )
    assert response.status_code == 401


def test_webhook_unknown_event_ignored(client):
    with patch('app.routes.revolut.revolut_client.verify_webhook', return_value=True):
        response = client.post(
            '/api/v1/revolut/webhooks',
            json={'event': 'SOME_OTHER_EVENT', 'order_id': 'x'},
            headers={'revolut-signature': 'dummy'},
        )
    assert response.status_code == 200
