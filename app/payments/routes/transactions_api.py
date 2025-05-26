from datetime import datetime
import logging
import re

from flask import jsonify, request
from flask_security import current_user, login_required, roles_required

from app.tools import prepare_datatables_query

from app import db
from .. import bp_api_admin, bp_api_user
from app.users.models.user import User
from ..models.transaction import Transaction
from ..validators.transaction import TransactionValidator

@bp_api_admin.route('/transaction', defaults={'transaction_id': None})
@bp_api_admin.route('/transaction/<int:transaction_id>')
@login_required
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

@bp_api_admin.route('/transaction', methods=['POST'])
@login_required
@roles_required('admin')
def admin_save_transaction():
    logger = logging.getLogger('admin_save_transaction')
    payload = request.get_json()
    with TransactionValidator(request) as validator:
        if not validator.validate():
            error = {
                'data': [],
                'error': "Couldn't create a Payment",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            }
            return jsonify(error)
    logger.info("Creating transaction by %s with data %s", current_user, payload)
    if isinstance(payload['amount'], str):
        payload['amount'] = re.sub(
            r'[\s,]', '', payload['amount'])
    customer = User.query.get(payload['customer_id'])

    transaction = Transaction(
        customer=customer,
        customer_balance=customer.balance + int(payload['amount']),
        amount=int(payload['amount']),
        user=current_user,
        when_created=datetime.now()
    )

    db.session.add(transaction)
    db.session.commit()
    return jsonify({'data': [transaction.to_dict()]})
