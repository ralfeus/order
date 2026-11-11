'''Signal handlers for EurocargoShipping'''
import logging
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# Eurocargo accepts at most this many inventory lines per shipment
MAX_ITEMS = 100
_LINE_BREAKS = re.compile(r'\s*[\r\n\t]+\s*')
_CENTS = Decimal('0.01')
_GRAMS = Decimal('0.001')


# ---------------------------------------------------------------------------
# sale_order_packed → no-op for EurocargoShipping
# ---------------------------------------------------------------------------

def on_sale_order_packed(order, **_extra):
    '''For EurocargoShipping, nothing to do at pack time.
    The carrier and shipping cost are determined later in eurocargo_management
    when the customer selects a carrier on the payment page.'''
    pass


# ---------------------------------------------------------------------------
# sale_order_shipped → create ECmgmt shipment record(s), no carrier yet
# ---------------------------------------------------------------------------

def on_sale_order_shipped(order, **_extra):
    '''When a EurocargoShipping order is shipped, create one shipment per
    physical box in eurocargo_management.  No carrier or cost is set at this
    point: the customer chooses a carrier on the Eurocargo payment page, and
    Eurocargo prices both legs itself.
    '''
    from .models.eurocargo_shipping import EurocargoShipping

    if not isinstance(order.shipping, EurocargoShipping):
        return

    missing = _missing_fields(order)
    if missing:
        logger.error('Eurocargo shipment for order %s not created: missing %s',
                     order.id, ', '.join(missing))
        return

    eurocargo_api_url = current_app.config.get('EUROCARGO_API_URL', 'http://localhost:8000')
    eurocargo_base_url = current_app.config.get('EUROCARGO_BASE_URL', 'http://localhost:3000')
    eurocargo_api_key = current_app.config.get('EUROCARGO_API_KEY', 'supersecretkey')

    units = list(_box_units(order.boxes))
    content_weight_per_unit_kg = order.total_weight / 1000 / len(units)
    common = _common_fields(order)
    items = _items(order)

    for box, seq in units:
        shipment_order_id = order.id if len(units) == 1 else f'{order.id}-{seq}'
        payload = {
            'order_id': shipment_order_id,
            **common,
            'weight_kg': str(round(max(content_weight_per_unit_kg, _volumetric_kg(box)), 3)),
            'length_cm': box.length,
            'width_cm': box.width,
            'height_cm': box.height,
        }
        # Box contents are unknown per box: the whole inventory travels with
        # the first box; Eurocargo derives its declared cost from the items.
        if seq == 1:
            if items:
                payload['items'] = items
        else:
            payload['declared_cost_eur'] = '0'

        _post_shipment(order, shipment_order_id, payload,
                       eurocargo_api_url, eurocargo_base_url,
                       store_url=seq == 1, api_key=eurocargo_api_key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _missing_fields(order) -> list[str]:
    '''Fields Eurocargo requires from API partners that the order lacks.'''
    missing = []
    if not order.email:
        missing.append('email')
    if not _single_line(order.address):
        missing.append('address')
    if not order.boxes:
        missing.append('boxes')
    elif not all(b.length and b.width and b.height for b in order.boxes):
        missing.append('box dimensions')
    return missing


def _single_line(value: Optional[str]) -> str:
    '''Eurocargo takes the address as one line: join line breaks with ", ".'''
    return _LINE_BREAKS.sub(', ', (value or '').strip()).strip(', ')


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
    by the customer on the Eurocargo payment page, not at creation time.
    '''
    return {
        'customer_name': order.customer_name,
        'email': order.email,
        'address': _single_line(order.address),
        'city': order.city_eng or '',
        'country': order.country_id or '',
        'zip': order.zip or '',
        'phone': order.phone or None,
        'tracking_code': order.tracking_id,
        'container_id': f'CNT-{order.invoice_id or order.id}',
    }


def _eur_rate(order) -> Optional[float]:
    '''Base currency → EUR rate valid when the order was created, or None.'''
    from app import db
    from app.currencies.models.currency import Currency
    eur = db.session.get(Currency, 'EUR')
    return eur.get_rate(order.when_created) if eur else None


def _items(order) -> list[dict]:
    '''Build the Eurocargo inventory from the order's shipped products.

    Lines of the same product at the same price are merged.  Lines beyond
    Eurocargo's limit are folded into one "Other items" line.
    '''
    from app.orders.models.order_product import OrderProductStatus

    ops = [op for op in order.order_products
           if op.status != OrderProductStatus.unavailable]
    if not ops:
        return []
    rate = _eur_rate(order)
    if rate is None:
        logger.error('Eurocargo items for order %s not sent: no EUR rate', order.id)
        return []
    rate = Decimal(str(rate))

    lines: dict[tuple, dict] = {}
    for op in ops:
        key = (op.product_id, op.price)
        if key in lines:
            lines[key]['quantity'] += op.quantity
            continue
        product = op.product
        lines[key] = {
            'name': (product.name_english or product.name or op.product_id)[:256],
            'weight_kg': (Decimal(product.weight or 0) / 1000).quantize(_GRAMS),
            'price_eur': (Decimal(op.price) * rate).quantize(_CENTS, ROUND_HALF_UP),
            'quantity': op.quantity,
        }
    items = list(lines.values())

    if len(items) > MAX_ITEMS:
        kept, rest = items[:MAX_ITEMS - 1], items[MAX_ITEMS - 1:]
        items = kept + [{
            'name': 'Other items',
            'weight_kg': sum(i['weight_kg'] * i['quantity'] for i in rest),
            'price_eur': sum(i['price_eur'] * i['quantity'] for i in rest),
            'quantity': 1,
        }]

    return [{**i, 'weight_kg': str(i['weight_kg']), 'price_eur': str(i['price_eur'])}
            for i in items]


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
