'''Admin API routes for SeparateShipping'''
from flask import current_app, jsonify, request
from flask_security import login_required, roles_required

import requests

from app import db

from .. import bp_api_admin
from ..models.separate_shipping import SeparateShipping


@bp_api_admin.route('/<int:shipping_id>', methods=['POST'])
@login_required
@roles_required('admin')
def admin_save(shipping_id):
    '''Save subtype_code for a SeparateShipping instance'''
    shipping = db.session.get(SeparateShipping, shipping_id)
    if not shipping:
        return jsonify({'error': f'Shipping {shipping_id} not found'}), 404

    payload = request.get_json() or {}
    shipping.subtype_code = payload.get('subtype_code') or None
    db.session.commit()
    return jsonify({'id': shipping.id, 'subtype_code': shipping.subtype_code})


@bp_api_admin.route('/shipment-types', methods=['GET'])
@login_required
@roles_required('admin')
def proxy_shipment_types():
    '''Proxy to eurocargo /api/v1/shipment-types so the browser never needs
    to know the backend URL of eurocargo.'''
    eurocargo_url = current_app.config.get('EUROCARGO_API_URL', 'http://localhost:8000')
    try:
        response = requests.get(f'{eurocargo_url}/api/v1/shipment-types', timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as exc:
        current_app.logger.warning('Could not fetch shipment types from eurocargo: %s', exc)
        return jsonify([])
