from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from .. import bp_api_admin, bp_api_user
from ..models.transaction import Transaction

@bp_api_admin.route('/transaction', defaults={'transaction_id': None})
@bp_api_admin.route('/transaction/<int:transaction_id>')
@roles_required('admin')
def admin_get_transactions(transaction_id):
    '''
    Returns all or selected payments in JSON
    '''
    transactions = Transaction.query
    if transaction_id is not None:
        transactions = transactions.filter_by(id=transaction_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), transactions)))

@bp_api_user.route('/transaction', defaults={'transaction_id': None})
@bp_api_user.route('/transaction/<int:transaction_id>')
@login_required
def user_get_transactions(transaction_id):
    '''
    Returns all or selected payments in JSON
    '''
    transactions = Transaction.query.filter_by(customer=current_user)
    if transaction_id is not None:
        transactions = transactions.filter_by(id=transaction_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), transactions)))
