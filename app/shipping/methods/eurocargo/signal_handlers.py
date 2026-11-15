'''Signal handlers for EurocargoShipping'''
import logging
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import requests
from flask import current_app

from app.orders.models.order import Order

logger = logging.getLogger(__name__)

# Eurocargo accepts at most this many inventory lines per shipment
MAX_ITEMS = 100
_LINE_BREAKS = re.compile(r'\s*[\r\n\t]+\s*')
_CENTS = Decimal('0.01')
_GRAMS = Decimal('0.001')
# Order params holding Eurocargo shipment references.  The URL of the first
# box is shown to the customer; every box's token is kept for later updates.
URL_PARAM = 'eurocargo.shipment_url'
TOKEN_PARAM_PREFIX = 'eurocargo.shipment_token.'
# Shipments that couldn't be deleted: <prefix><token> = order ID
DELETE_FAILED_PARAM_PREFIX = 'eurocargo.delete_failed.'


# ---------------------------------------------------------------------------
# status changed to packed → create ECmgmt shipment record(s), no carrier yet
# ---------------------------------------------------------------------------

def on_sale_order_packed(order, old_status=None, new_status=None, **_extra):
    '''When a EurocargoShipping order is packed or ready to ship or shipped,
    create one shipment per physical box in eurocargo_management unless it's
    already created.  No carrier or cost is set at this point: the customer
    chooses a carrier on the Eurocargo payment page, and Eurocargo prices both
    legs itself.

    An order that already has a shipment (e.g. re-packed after
    ready_to_ship) gets no new one.

    For ready_to_ship / shipped transitions the shipment is created only when
    the order skipped the packed step entirely (old_status < packed).  If the
    order already passed through packed the packed handler was (or should have
    been) responsible.
    '''
    from app.orders.models.order_status import OrderStatus
    from .models.eurocargo_shipping import EurocargoShipping

    if not isinstance(order.shipping, EurocargoShipping):
        return
    if has_shipment(order):
        logger.info('Eurocargo shipment for order %s already exists, not creating',
                    order.id)
        return
    if new_status in (OrderStatus.ready_to_ship, OrderStatus.shipped):
        if old_status is not None and old_status.value >= OrderStatus.packed.value:
            logger.info('Order %s already reached packed, skipping shipment creation on %s',
                        order.id, new_status)
            return
    create_shipments(order)


# ---------------------------------------------------------------------------
# sale_order_shipping_changed → delete shipment(s) or create them
# ---------------------------------------------------------------------------

def on_sale_order_shipping_changed(order, old_shipping=None, **_extra):
    '''Keep Eurocargo in line with the order's new shipping method.

    * Not Eurocargo any more: every existing shipment is deleted.  The
      shipping method can't change once the order is handed over for
      shipping, so a paid or received shipment never gets here.
    * Changed to Eurocargo on a packed order without a shipment: shipments
      are created, as if the order was packed now.
    '''
    from app.orders.models.order_status import OrderStatus
    from .models.eurocargo_shipping import EurocargoShipping

    if not isinstance(order.shipping, EurocargoShipping):
        if has_shipment(order):
            delete_shipments(order)
        return
    if order.status == OrderStatus.packed and not has_shipment(order):
        create_shipments(order)


def delete_shipments(order):
    '''Delete every Eurocargo shipment of *order*.

    References of the shipments are removed from the order params.  A
    shipment Eurocargo doesn't know (404) counts as deleted.  Any other
    failure is logged and the token is kept as
    ``eurocargo.delete_failed.<token>`` for a later retry; it never raises.
    '''
    eurocargo_api_url = current_app.config.get('EUROCARGO_API_URL', 'http://localhost:8000')
    api_key = current_app.config.get('EUROCARGO_API_KEY', 'supersecretkey')

    for token in _shipment_tokens(order):
        try:
            response = requests.delete(
                f'{eurocargo_api_url}/api/v1/shipments/{token}',
                headers={'X-API-Key': api_key},
                timeout=10,
            )
            logger.info('Eurocargo delete response for %s (order %s): %s %s',
                        token, order.id, response.status_code, response.text)
            if response.status_code == 404:
                logger.warning('Eurocargo shipment %s of order %s not found, '
                               'treating as deleted', token, order.id)
            else:
                response.raise_for_status()
                logger.info('Deleted eurocargo shipment %s of order %s',
                            token, order.id)
        except Exception as exc:
            logger.error('Failed to delete eurocargo shipment %s of order %s: %s',
                         token, order.id, exc)
            order.params[f'{DELETE_FAILED_PARAM_PREFIX}{token}'] = order.id

    for name in [n for n in order.params
                 if n == URL_PARAM or n.startswith(TOKEN_PARAM_PREFIX)]:
        order.params.pop(name)


def _shipment_tokens(order) -> list[str]:
    '''Tokens of all shipments of *order*, unique, in box order.  For orders
    shipped before tokens were stored the token is taken from the URL.'''
    params = order.params or {}
    names = sorted((n for n in params if n.startswith(TOKEN_PARAM_PREFIX)),
                   key=lambda n: int(n[len(TOKEN_PARAM_PREFIX):]))
    tokens = [params[n] for n in names]
    if not tokens and params.get(URL_PARAM):
        tokens = [params[URL_PARAM].rstrip('/').rsplit('/', 1)[-1]]
    return list(dict.fromkeys(tokens))


def has_shipment(order) -> bool:
    '''True if a Eurocargo shipment was created for *order*.  Orders shipped
    before tokens were stored are recognised by the shipment URL.'''
    params = order.params or {}
    return URL_PARAM in params or \
        any(name.startswith(TOKEN_PARAM_PREFIX) for name in params)


def create_shipments(order):
    '''Create one eurocargo_management shipment per physical box of *order*,
    regardless of the order's shipping method or status.

    On success the shipment URL of the first box is stored in
    ``order.params['eurocargo.shipment_url']`` and the token of each box in
    ``order.params['eurocargo.shipment_token.<seq>']``.  Errors are logged,
    not raised.
    '''
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
            payload['description'] = (
                f'Part {seq} of {len(units)} of order {order.id}, '
                f'contents declared on {order.id}-1')

        _post_shipment(order, seq, shipment_order_id, payload,
                       eurocargo_api_url, eurocargo_base_url,
                       api_key=eurocargo_api_key)


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


def _common_fields(order: Order) -> dict:
    '''Return the recipient fields shared by every shipment payload.

    ``shipment_type_code`` is intentionally omitted: the carrier is chosen
    by the customer on the Eurocargo payment page, not at creation time.
    '''
    return {
        'customer_name': order.customer_name,
        'email': order.email,
        'address': _single_line(str(order.address)),
        'city': order.city_eng or '',
        'country': order.country_id or '',
        'zip': order.zip or '',
        'phone': order.phone or None,
        'tracking_code': order.tracking_id,
        'container_id': f'CNT-{order.invoice and order.invoice.export_id or order.invoice_id or order.id}',
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


def _post_shipment(order, seq, shipment_order_id, payload,
                   eurocargo_api_url, eurocargo_base_url, api_key=''):
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
        token = data.get('token') or shipment_url.rstrip('/').rsplit('/', 1)[-1]
        order.params[f'{TOKEN_PARAM_PREFIX}{seq}'] = token
        if seq == 1:
            order.params[URL_PARAM] = shipment_url
        logger.info('Created eurocargo shipment %s: %s', shipment_order_id, shipment_url)
    except Exception as exc:
        logger.error('Failed to create eurocargo shipment %s: %s', shipment_order_id, exc)
