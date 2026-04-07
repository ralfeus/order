'''Signal handlers for SeparateShipping'''
import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def on_sale_order_packed(order, **_extra):
    '''When an order with SeparateShipping is packed:
    1. Calculate actual shipping cost and persist it on the order.
    2. Create a shipment record in eurocargo_management.
    '''
    from .models.separate_shipping import SeparateShipping

    if not isinstance(order.shipping, SeparateShipping):
        return

    # --- 1. Calculate and store actual shipping cost ---
    from common.exceptions import NoShippingRateError
    try:
        actual_cost = order.shipping.get_actual_shipping_cost(
            order.country_id, order.total_weight
        )
    except NoShippingRateError:
        actual_cost = 0
        logger.warning('No shipping rate for order %s (%s, %sg)',
                       order.id, order.country_id, order.total_weight)

    order.shipping_base_currency = actual_cost

    if order.user_currency_code:
        from app.currencies.models.currency import Currency
        user_currency = Currency.query.filter_by(code=order.user_currency_code).first()
        if user_currency:
            places = user_currency.decimal_places or 2
            order.shipping_user_currency = round(
                actual_cost * float(user_currency.rate), places
            )

    order.total_base_currency = (order.subtotal_base_currency or 0) + actual_cost
    if order.user_currency_code:
        order.total_user_currency = (
            (order.subtotal_user_currency or 0) + (order.shipping_user_currency or 0)
        )

    # --- 2. Create shipment in eurocargo ---
    eurocargo_api_url = current_app.config.get('EUROCARGO_API_URL', 'http://localhost:8000')
    eurocargo_base_url = current_app.config.get('EUROCARGO_BASE_URL', 'http://localhost:3000')

    from app.currencies.models.currency import Currency
    eur = Currency.query.filter_by(code='EUR').first()
    amount_eur = round(actual_cost * float(eur.rate), 2) if eur else 0.0

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
        'tracking_code': order.tracking_id,
        'amount_eur': str(amount_eur),
    }

    try:
        response = requests.post(
            f'{eurocargo_api_url}/api/v1/shipments',
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        shipment_url = data.get('shipment_url') or \
            f'{eurocargo_base_url}/shipments/{data["token"]}'
        order.params['eurocargo.shipment_url'] = shipment_url
        logger.info('Created eurocargo shipment for order %s: %s', order.id, shipment_url)
    except Exception as exc:
        logger.exception(
            'Failed to create eurocargo shipment for order %s: %s', order.id, exc
        )
