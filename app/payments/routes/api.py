'''
Contains API endpoint routes of the transaction services
'''
from datetime import datetime
import os.path

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.currencies.models import Currency
from app.orders.models import Order, OrderStatus
from app.payments import bp_api_admin, bp_api_user
from app.payments.models import PaymentMethod, Transaction, TransactionStatus

from app.tools import rm, write_to_file

@bp_api_admin.route('/', defaults={'transaction_id': None}, strict_slashes=False)
@bp_api_admin.route('/<int:transaction_id>')
@roles_required('admin')
def admin_get_transactions(transaction_id):
    '''
    Returns all or selected transactions in JSON
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
        if order.total_krw <= transaction.user.balance and \
           order.status == OrderStatus.pending:
            transaction.user.balance -= order.total_krw
            order.status = OrderStatus.paid
            messages.append(f"Order <{order.id}> is PAID")
            # db.session.add(Transaction(
            #     user=transaction.user,
            #     orders=[order],
            #     amount_received_krw=-order.total_krw,
            #     status=TransactionStatus.approved
            # ))

@bp_api_user.route('/', defaults={'transaction_id': None}, strict_slashes=False)
@bp_api_user.route('/<int:transaction_id>')
@login_required
def user_get_transactions(transaction_id):
    '''
    Returns user's or all transactions in JSON
    '''
    transactions = Transaction.query \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)
    transactions = transactions.filter_by(user=current_user)
    return jsonify(list(map(lambda tran: tran.to_dict(), transactions)))

@bp_api_user.route('', methods=['POST'])
@login_required
def user_create_payment():
    payload = request.get_json()
    if not payload:
        abort(Response('No payment data was provided', status=400))
    currency = Currency.query.get(payload['currency_code'])
    if not currency:
        abort(Response(f"No currency <{payload['currency_code']}> was found", status=400))

    transaction = Transaction(
        user=current_user,
        changed_by=current_user,
        orders=Order.query.filter(Order.id.in_(payload['orders'])).all(),
        currency=currency,
        amount_sent_original=payload['amount_original'],
        amount_sent_krw=float(payload['amount_original']) / float(currency.rate),
        payment_method=payload['payment_method'],
        status=TransactionStatus.pending,
        when_created=datetime.now()
    )
    db.session.add(transaction)
    db.session.commit()
    return jsonify(transaction.to_dict())

@bp_api_user.route('/<int:transaction_id>', methods=['POST'])
@login_required
def user_save_transaction(transaction_id):
    '''
    Saves updates in transaction
    '''
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(404)

    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(
            f"Can't update transaction in state <{transaction.status}>", status=409))
    if payload['status'] == 'cancelled':
        transaction.status = TransactionStatus.cancelled

    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    db.session.commit()

    return jsonify(transaction.to_dict())

@bp_api_user.route('/<int:transaction_id>/evidence', methods=['POST'])
@login_required
def user_upload_transaction_evidence(transaction_id):
    transaction = Transaction.query.get(transaction_id)
    if not current_user.has_role('admin') and \
        current_user != transaction.user:
        abort(403)
    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(
            f"Can't update transaction in state <{transaction.status}>", status=409))
    if request.files and request.files['file'] and request.files['file'].filename:
        file = request.files['file']
        rm(transaction.proof_image)
        image_data = file.read()
        file_name = os.path.join(
            current_app.config['UPLOAD_PATH'],
            str(current_user.id),
            datetime.now().strftime('%Y-%m-%d.%H%M%S.%f')) + \
            ''.join(os.path.splitext(file.filename)[1:])
        write_to_file(file_name, image_data)
    
        transaction.proof_image = file_name
        transaction.when_changed = datetime.now()
        transaction.changed_by = current_user
        db.session.commit()
    else:
        abort(Response("No file is uploaded", status=400))
    return jsonify({})

@bp_api_user.route('/method')
@login_required
def get_payment_methods():
    payment_methods = PaymentMethod.query
    return jsonify(list(map(lambda pm: pm.to_dict(), payment_methods)))