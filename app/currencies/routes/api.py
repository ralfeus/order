from datetime import datetime
from functools import reduce
from more_itertools import map_reduce
import openpyxl

from flask import Response, abort, jsonify, request, send_file
from flask_security import roles_required

from app import db
from app.currencies import bp_api_admin, bp_api_user
from app.currencies.models import Currency
from app.models import Order

@bp_api_admin.route('/', defaults={'currency_id': None}, strict_slashes=False)
@bp_api_admin.route('/<currency_id>')
@roles_required('admin')
def get_currencies(currency_id):
    '''
    Returns all or selected currencies in JSON:
    {
        id: currency ID,
        [
            code: currency code
            name: name of currency,
            rate: default KRW
        ]
    }
    '''
    currencies = Currency.query.all() \
        if currency_id is None \
        else Currency.query.filter_by(id=currency_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), currencies)))

@bp_api_admin.route('/<currency_id>', methods=['POST'])
@roles_required('admin')
def save_invoice_item(currency_id):
    '''
    Creates or modifies existing currency
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))
    currency = Currency.query.get(currency_id)
    if not currency:
        abort(Response(f'No currency <{currency_id}> was found', status=404))
    if currency_id != 'new':
        currency_id = invoice.invoice_items.filter_by(id=invoice_item_id).first()
        if not invoice_item:
            abort(Response(f'No invoice item <{invoice_item_id}> was found', status=404))
    else:
        invoice_item = CurrencyItem(currency=currency, when_created=datetime.now())
    
    for key, value in payload.items():
        if getattr(invoice_item, key) != value:
            setattr(invoice_item, key, value)
            invoice_item.when_changed = datetime.now()
    if invoice_item_id == 'new':
        db.session.add(invoice_item)
    db.session.commit()
    return jsonify(invoice_item.to_dict())

@bp_api_admin.route('/<invoice_id>/item/<invoice_item_id>', methods=['DELETE'])
@roles_required('admin')
def delete_invoice_item(invoice_id, invoice_item_id):
    '''
    Deletes existing invoice item
    '''
    invoice = Currency.query.get(invoice_id)
    if not invoice:
        abort(Response(f'No invoice <{invoice_id}> was found', status=404))
    invoice_item = invoice.invoice_items.filter_by(id=invoice_item_id).first()
    if not invoice_item:
        abort(Response(f'No invoice item<{invoice_item_id}> was found', status=404))
    db.session.delete(invoice_item)
    db.session.commit()
    return jsonify({
        'status': 'success'
    })
