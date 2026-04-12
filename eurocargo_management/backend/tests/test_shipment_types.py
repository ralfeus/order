'''Tests for GET /api/v1/shipment-types and GET /api/v1/shipment-types/{id}'''


def test_list_shipment_types_empty(client):
    response = client.get('/api/v1/shipment-types')
    assert response.status_code == 200
    assert response.json() == []


def test_list_shipment_types_returns_all(client, shipment_type):
    response = client.get('/api/v1/shipment-types')
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['code'] == 'GLS'
    assert data[0]['name'] == 'GLS Parcel'
    assert data[0]['enabled'] is True


def test_get_shipment_type_found(client, shipment_type):
    response = client.get(f'/api/v1/shipment-types/{shipment_type.id}')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == shipment_type.id
    assert data['code'] == 'GLS'


def test_get_shipment_type_not_found(client):
    response = client.get('/api/v1/shipment-types/9999')
    assert response.status_code == 404
    assert 'not found' in response.json()['detail'].lower()
