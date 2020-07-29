'''
Contains api endpoint routes of the application
'''
from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_login import current_user, login_required

from app import app, db
from app.models import \
    Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
    ShippingRate, Transaction, TransactionStatus

@app.route('/api/v1/admin/transaction', defaults={'transaction_id': None})
@app.route('/api/v1/admin/transaction/<int:transaction_id>')
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

@app.route('/api/v1/admin/transaction/<int:transaction_id>', methods=['POST'])
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
