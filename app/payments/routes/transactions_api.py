from flask import jsonify, request
from flask_security import current_user, login_required, roles_required

from app.tools import prepare_datatables_query

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
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_transactions(transactions, request.values)

    return jsonify([entry.to_dict() for entry in transactions])

def _filter_transactions(transactions, filter_params):
    transactions, records_total, records_filtered = prepare_datatables_query(
        transactions, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict() for entry in transactions]
    })

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
