'''
Contains api endpoint routes of the application
'''
from datetime import datetime

from flask import abort, jsonify, request
from flask_login import current_user, login_required

from app import app, db
from app.models import \
    Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
    ShippingRate, Transaction, TransactionStatus

@app.route('/api/v1.0/admin/transaction', defaults={'transaction_id': None})
@app.route('/api/v1.0/admin/transaction/<int:transaction_id>')
@login_required
def get_transactions(transaction_id):
    '''
    Returns all transactions in JSON:
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
    payload = request.get_json()
    transactions = Transaction.query \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)
    transactions = transactions.all()

    return jsonify(list(map(lambda entry: {
        'id': entry.id,
        'user_id': entry.user_id,
        'amount_original': entry.amount_original,
        'amount_original_string': entry.currency.format(entry.amount_original),
        'amount_krw': entry.amount_krw,
        'currency_code': entry.currency.code,
        'proof_image': entry.proof_image,
        'status': entry.status.name,
        'when_created': entry.when_created.strftime('%Y-%m-%d %H:%M:%S'),
        'when_changed': entry.when_changed.strftime('%Y-%m-%d %H:%M:%S') if entry.when_changed else ''
    }, transactions)))

@app.route('/api/v1.0/admin/transaction/<int:transaction_id>', methods=['POST'])
@login_required
def save_transaction(transaction_id):
    '''
    Saves updates in transaction
    '''
    if current_user.username != 'admin':
        abort(403)
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(404)
    if (payload and payload.get('context') == 'admin' and
        current_user.username == 'admin'):
        transaction.amount_original = payload['amount_original']
        transaction.currency = Currency.query.get(payload['currency_code'])
        transaction.amount_krw = payload['amount_krw']
        transaction.status = payload['status']
    else:
        if payload['status'] == 'cancelled':
            transaction.status = TransactionStatus.cancelled
    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    db.session.commit()

    return jsonify({
        'id': transaction.id,
        'user_id': transaction.user_id,
        'amount_original': transaction.amount_original,
        'amount_original_string': transaction.currency.format(transaction.amount_original),
        'amount_krw': transaction.amount_krw,
        'currency_code': transaction.currency.code,
        'proof_image': transaction.proof_image,
        'status': transaction.status.name,
        'when_created': transaction.when_created.strftime('%Y-%m-%d %H:%M:%S'),
        'when_changed': transaction.when_changed.strftime('%Y-%m-%d %H:%M:%S') if transaction.when_changed else ''
    })