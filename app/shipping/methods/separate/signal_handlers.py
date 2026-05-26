'''Signal handlers for SeparateShipping'''
import logging

import requests
from flask import current_app

from app.settings.models.setting import Setting

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# sale_order_packed → no-op for SeparateShipping
# ---------------------------------------------------------------------------

def on_sale_order_packed(order, **_extra):
    '''For SeparateShipping, nothing to do at pack time.
    The carrier and shipping cost are determined later in eurocargo_management
    when the customer selects a carrier on the payment page.'''
    pass


# ---------------------------------------------------------------------------
# sale_order_shipped → create ECmgmt shipment record(s), no carrier yet
# ---------------------------------------------------------------------------

def on_sale_order_shipped(order, **_extra):
    '''When a SeparateShipping order is shipped, create one or more shipment
    records in eurocargo_management.  No carrier or cost is set at this point:
    the customer will choose a carrier on the ECmgmt payment page, which then
    calculates and presents the cost.
    '''
    from .models.separate_shipping import SeparateShipping

    if not isinstance(order.shipping, SeparateShipping):
        return

    eurocargo_api_url = current_app.config.get('EUROCARGO_API_URL', 'http://localhost:8000')
    eurocargo_base_url = current_app.config.get('EUROCARGO_BASE_URL', 'http://localhost:3000')
    eurocargo_api_key = current_app.config.get('EUROCARGO_API_KEY', 'supersecretkey')

    shipping_id = order.shipping.id
    first_leg_raw = Setting.get(f'shipping.separate.{shipping_id}.first_leg')
    first_leg = float(first_leg_raw) if first_leg_raw else None

    is_multi_box = len(order.boxes) > 1 or (
        len(order.boxes) == 1 and order.boxes[0].quantity > 1
    )

    if is_multi_box:
        _create_multi_box_shipments(order, eurocargo_api_url, eurocargo_base_url,
                                    eurocargo_api_key, first_leg=first_leg)
    else:
        _create_single_shipment(order, eurocargo_api_url, eurocargo_base_url,
                                eurocargo_api_key, first_leg=first_leg)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _volumetric_kg(box):
    '''Return volumetric weight in kg for a single box unit: L × W × H / 5000.'''
    if box.length and box.width and box.height:
        return box.length * box.width * box.height / 5000
    return 0


def _box_units(boxes):
    '''Expand box list into individual (box, seq) tuples, one per physical unit.

    A box with quantity=3 yields three entries with the same box object.
    seq is 1-based and increments across all box entries.
    '''
    seq = 0
    for box in boxes:
        for _ in range(box.quantity):
            seq += 1
            yield box, seq


def _common_fields(order):
    '''Return the recipient fields shared by every shipment payload.

    ``shipment_type_code`` is intentionally omitted: the carrier is chosen
    by the customer on the ECmgmt payment page, not at creation time.
    '''
    return {
        'customer_name': order.customer_name,
        'email': order.email or '',
        'address': order.address or '',
        'city': order.city_eng or '',
        'country': order.country_id or '',
        'zip': order.zip or '',
        'phone': order.phone,
        'tracking_code': order.tracking_id,
    }


def _create_single_shipment(order, eurocargo_api_url, eurocargo_base_url, api_key='',
                            first_leg=None):
    '''Single physical box (or no box info): one shipment with the original order_id.'''
    weight_kg = round(order.total_weight / 1000, 3)

    payload = {
        'order_id': order.id,
        **_common_fields(order),
        'weight_kg': str(weight_kg),
    }

    if order.boxes:
        box = order.boxes[0]
        vol_kg = _volumetric_kg(box)
        weight_kg = round(max(weight_kg, vol_kg), 3)
        payload['weight_kg'] = str(weight_kg)
        if box.length and box.width and box.height:
            payload['length_cm'] = box.length
            payload['width_cm'] = box.width
            payload['height_cm'] = box.height

    if first_leg is not None:
        payload['additional_cost_eur'] = str(round(weight_kg * first_leg, 2))

    _post_shipment(order, order.id, payload, eurocargo_api_url, eurocargo_base_url,
                   store_url=True, api_key=api_key)


def _create_multi_box_shipments(order, eurocargo_api_url, eurocargo_base_url, api_key='',
                                first_leg=None):
    '''Multiple physical boxes: one shipment per unit, order_id = <order_id>-<seq>.'''
    total_units = sum(b.quantity for b in order.boxes)
    content_weight_per_unit_kg = order.total_weight / 1000 / total_units
    first_url_stored = False

    for box, seq in _box_units(order.boxes):
        vol_kg = _volumetric_kg(box)
        unit_weight_kg = round(max(content_weight_per_unit_kg, vol_kg), 3)
        shipment_order_id = f'{order.id}-{seq}'

        payload = {
            'order_id': shipment_order_id,
            **_common_fields(order),
            'weight_kg': str(unit_weight_kg),
        }
        if box.length and box.width and box.height:
            payload['length_cm'] = box.length
            payload['width_cm'] = box.width
            payload['height_cm'] = box.height

        if first_leg is not None:
            payload['additional_cost_eur'] = str(round(unit_weight_kg * first_leg, 2))

        _post_shipment(order, shipment_order_id, payload,
                       eurocargo_api_url, eurocargo_base_url,
                       store_url=not first_url_stored, api_key=api_key)
        first_url_stored = True


def _post_shipment(order, shipment_order_id, payload,
                   eurocargo_api_url, eurocargo_base_url, store_url, api_key=''):
    try:
        response = requests.post(
            f'{eurocargo_api_url}/api/v1/shipments',
            json=payload,
            headers={'X-API-Key': api_key},
            timeout=10,
        )
        logger.info('Eurocargo response for %s: %s %s',
                    shipment_order_id, response.status_code, response.text)
        response.raise_for_status()
        data = response.json()
        shipment_url = data.get('shipment_url') or \
            f'{eurocargo_base_url}/shipments/{data["token"]}'
        if store_url:
            order.params['eurocargo.shipment_url'] = shipment_url
        logger.info('Created eurocargo shipment %s: %s', shipment_order_id, shipment_url)
    except Exception as exc:
        logger.error('Failed to create eurocargo shipment %s: %s', shipment_order_id, exc)
