'''Signal handlers for SeparateShipping'''
import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def on_sale_order_packed(order, **_extra):
    '''When an order with SeparateShipping is packed:
    1. Create a shipment record in eurocargo_management.
    '''
    from .models.separate_shipping import SeparateShipping

    if not isinstance(order.shipping, SeparateShipping):
        return

    # --- 1. Create shipment in eurocargo ---
    eurocargo_api_url = current_app.config.get('EUROCARGO_API_URL', 'http://localhost:8000')
    eurocargo_base_url = current_app.config.get('EUROCARGO_BASE_URL', 'http://localhost:3000')

    weight_kg = round(order.total_weight / 1000, 3)  # grams → kg

    payload = {
        'order_id': order.id,
        'customer_name': order.customer_name,
        'email': order.email or '',
        'address': order.address or '',
        'city': order.city_eng or '',
        'country': order.country_id or '',
        'zip': order.zip or '',
        'phone': order.phone,
        'shipment_type_code': order.shipping.subtype_code or '',
        'weight_kg': str(weight_kg),
        'tracking_code': order.tracking_id,
    }

    try:
        response = requests.post(
            f'{eurocargo_api_url}/api/v1/shipments',
            json=payload,
            timeout=10,
        )
        logger.info('Separate shipping response:')
        logger.info('Status code: %s', response.status_code)
        logger.info('Response body: %s', response.text)
        response.raise_for_status()
        data = response.json()
        shipment_url = data.get('shipment_url') or \
            f'{eurocargo_base_url}/shipments/{data["token"]}'
        order.params['eurocargo.shipment_url'] = shipment_url
        logger.info('Created eurocargo shipment for order %s: %s', order.id, shipment_url)
    except Exception as exc:
        logger.error(
            'Failed to create eurocargo shipment for order %s: %s', order.id, exc
        )
