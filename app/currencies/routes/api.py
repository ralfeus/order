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

@bp_api_admin.route('/new/<float:usd_rate>', methods=['POST'])
@roles_required('admin')
def create_currency(usd_rate):
    '''
    Creates currency
    '''
    currency = Currency()
    currency_items = []
    currency.when_created = datetime.now()
    for currency in currencies:
        currency = currency
        invoice_items += [
            InvoiceItem(invoice=invoice, product=order_product.product,
                    price=round(order_product.price * usd_rate, 2),
                    quantity=order_product.quantity)
            for order_product in order.order_products]

    db.session.add(currency)
    db.session.add_all(currency_items)
    db.session.commit()
    return jsonify({
        'status': 'success',
        'invoice_id': invoice.id
    })

@bp_api_admin.route('/', defaults={'invoice_id': None}, strict_slashes=False)
@bp_api_admin.route('/<invoice_id>')
@roles_required('admin')
def get_invoices(invoice_id):
    '''
    Returns all or selected invoices in JSON:
    {
        id: invoice ID,
        [
            order_product_id: ID of the order product,
            name: name of the order product,
            quantity: quantity of order product,
            amount_krw: amount in KRW
        ]
    }
    '''
    invoices = Invoice.query.all() \
        if invoice_id is None \
        else Invoice.query.filter_by(id=invoice_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), invoices)))

@bp_api_admin.route('/<invoice_id>/item/<invoice_item_id>', methods=['POST'])
@roles_required('admin')
def save_invoice_item(invoice_id, invoice_item_id):
    '''
    Creates or modifies existing invoice item
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))
    invoice = Invoice.query.get(invoice_id)
    invoice_item = None
    if not invoice:
        abort(Response(f'No invoice <{invoice_id}> was found', status=404))
    if invoice_item_id != 'new':
        invoice_item = invoice.invoice_items.filter_by(id=invoice_item_id).first()
        if not invoice_item:
            abort(Response(f'No invoice item <{invoice_item_id}> was found', status=404))
    else:
        invoice_item = InvoiceItem(invoice=invoice, when_created=datetime.now())
    
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
    invoice = Invoice.query.get(invoice_id)
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
