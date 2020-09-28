'''
Contains API endpoint routes of the transaction services
'''
from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import current_user, roles_required

from app import db
from app.currencies.models import Currency
from app.transactions import bp_api_admin
from app.transactions.models import Transaction, TransactionStatus

@bp_api_admin.route('/', defaults={'transaction_id': None}, strict_slashes=False)
@bp_api_admin.route('/transaction/<int:transaction_id>')
@roles_required('admin')
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
    transactions = Transaction.query.all() \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), transactions)))

@bp_api_admin.route('/<int:transaction_id>', methods=['POST'])
@roles_required('admin')
def admin_save_transaction(transaction_id):
    '''
    Saves updates in user profile.
    '''
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(Response(f"No transaction <{transaction_id}> was found", status=404))
    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(f"Can't update transaction in state <{transaction.status}>", status=409))
    if not payload:
        abort(Response("No transaction data was provided", status=400))

    if payload.get('amount_original'):
        transaction.amount_sent_original = payload['amount_original']
    if payload.get('currency_code'):
        transaction.currency = Currency.query.get(payload['currency_code'])
    if payload.get('amount_krw'):
        transaction.amount_sent_krw = payload['amount_krw']
    if payload.get('amount_received_krw'):
        transaction.amount_received_krw = payload['amount_received_krw']
    if payload.get('status') and transaction.status != TransactionStatus.approved:
        transaction.status = payload['status'].lower()

    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    messages = []
    if transaction.status == TransactionStatus.approved:
        update_money(transaction, messages)

    db.session.commit()

    return jsonify({'transaction': transaction.to_dict(), 'message': messages})

def update_money(transaction, messages):
    transaction.user.balance += transaction.amount_received_krw
    for order in transaction.orders:
        if order.total_krw <= transaction.user.balance:
            transaction.user.balance -= order.total_krw
            order.status = 'Paid'
            messages.append(f"Order <{order.id}> is PAID")

