'''
Contains api endpoint routes of the application
'''
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import \
    Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
    ShippingRate, Transaction, TransactionStatus

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')

@admin_api.route('/order_product')
@login_required
def admin_get_order_products():
    '''
    Returns list of ordered items. So far implemented only for admins
    '''
    if current_user.username != 'admin':
        abort(403)
    order_products = OrderProduct.query.all()

    return jsonify(list(map(lambda order_product: {
        'order_id': order_product.order_id,
        'order_product_id': order_product.id,
        'customer': order_product.order.name,
        'subcustomer': order_product.subcustomer,
        'product_id': order_product.product_id,
        'product': order_product.product.name_english,
        'private_comment': order_product.private_comment,
        'public_comment': order_product.public_comment,
        'comment': order_product.order.comment,
        'quantity': order_product.quantity,
        'status': order_product.status
        }, order_products)))

@admin_api.route('/order_product/<int:order_product_id>', methods=['POST'])
@login_required
def admin_save_order_product(order_product_id):
    '''
    Modifies order products
    '''
    if current_user.username != 'admin':
        abort(403)
    result = None
    payload = request.get_json()
    order_product = OrderProduct.query.get(order_product_id)
    if order_product:
        if payload and payload.get('private_comment'):
            order_product.private_comment = payload['private_comment']
        order_product.public_comment = payload['public_comment']
        order_product.changed_at = datetime.now()
        try:
            db.session.commit()
            result = jsonify({
                'order_id': order_product.order_id,
                'order_product_id': order_product.id,
                'customer': order_product.order.name,
                'subcustomer': order_product.subcustomer,
                'product_id': order_product.product_id,
                'product': order_product.product.name_english,
                'private_comment': order_product.private_comment,
                'public_comment': order_product.public_comment,
                'quantity': order_product.quantity,
                'status': order_product.status
            })
        except Exception as e:
            result = jsonify({
                'status': 'error',
                'message': e
            })
            result.status_code = 500
    else:
        result = jsonify({
            'status': 'error',
            'message': f"Order product ID={order_product_id} wasn't found"
        })
        result.status_code = 404
    return result


@admin_api.route('/order_product/<int:order_product_id>/status/<order_product_status>', methods=['POST'])
def admin_set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    if current_user.username != 'admin':
        abort(403)
    order_product = OrderProduct.query.get(order_product_id)
    order_product.status = order_product_status
    db.session.add(OrderProductStatusEntry(
        order_product=order_product,
        status=order_product_status,
        # set_by=current_user,
        user_id=1,
        set_at=datetime.now()
    ))

    db.session.commit()

    return jsonify({
        'order_product_id': order_product_id,
        'order_product_status': order_product_status,
        'status': 'success'
    })

@admin_api.route('/order_product/<int:order_product_id>/status/history')
def admin_get_order_product_status_history(order_product_id):
    if current_user.username != 'admin':
        abort(403)
    history = OrderProductStatusEntry.query.filter_by(order_product_id=order_product_id)
    if history:
        return jsonify(list(map(lambda entry: {
            'set_by': entry.set_by.username,
            'set_at': entry.set_at,
            'status': entry.status
        }, history)))
    else:
        result = jsonify({
            'status': 'error',
            'message': f'No order product ID={order_product_id} found'
        })
        result.status_code = 404
        return result

@admin_api.route('/transaction', defaults={'transaction_id': None})
@admin_api.route('/transaction/<int:transaction_id>')
@login_required
def admin_get_transactions(transaction_id):
    '''
    Returns all or selected transactions in JSON:
    {
        id: transaction ID,
        user_id: ID of the transaction owner,
        currency: transaction original currency,
        amount_original: amount in original currency,
        amount_krw: amount in KRW at the time of transaction,
        status: transaction status ('pending', 'approved', 'rejected', 'cancelled')
    }
    '''
    if current_user.username != 'admin':
        abort(403)
    transactions = Transaction.query.all() \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), transactions)))

@admin_api.route('/transaction/<int:transaction_id>', methods=['POST'])
@login_required
def admin_save_transaction(transaction_id):
    '''
    Saves updates in transaction
    '''
    if current_user.username != 'admin':
        abort(403)
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(404)
    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(f"Can't update transaction in state <{transaction.status}>", status=409))
    if payload:
        if payload.get('amount_original'):
            transaction.amount_original = payload['amount_original']
        if payload.get('currency_code'):
            transaction.currency = Currency.query.get(payload['currency_code'])
        if payload.get('amount_krw'):
            transaction.amount_krw = payload['amount_krw']
        if payload.get('status') and transaction.status != TransactionStatus.approved:
            transaction.status = payload['status'].lower()
    else:
        abort(400)
    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    db.session.commit()

    return jsonify(transaction.to_dict())
