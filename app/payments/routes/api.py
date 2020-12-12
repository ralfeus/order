'''
Contains API endpoint routes of the payment services
'''
from datetime import datetime
import os.path

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.currencies.models import Currency
from app.orders.models import Order, OrderStatus
from app.payments import bp_api_admin, bp_api_user
from app.payments.models import PaymentMethod, Payment, PaymentStatus

from app.exceptions import PaymentNoReceivedAmountException
from app.tools import rm, write_to_file

@bp_api_admin.route('/', defaults={'payment_id': None}, strict_slashes=False)
@bp_api_admin.route('/<int:payment_id>')
@roles_required('admin')
def admin_get_payments(payment_id):
    '''
    Returns all or selected payments in JSON
    '''
    payments = Payment.query
    if payment_id is not None:
        payments = payments.filter_by(id=payment_id)

    if request.values.get('order_id'):
        payments = payments.filter(
            Payment.orders.has(Order.id == request.values['order_id']))

    return jsonify(list(map(lambda entry: entry.to_dict(), payments)))

@bp_api_admin.route('/<int:payment_id>', methods=['POST'])
@roles_required('admin')
def admin_save_payment(payment_id):
    '''
    Saves updates in user profile.
    '''
    payload = request.get_json()
    payment = Payment.query.get(payment_id)
    if not payment:
        abort(Response(f"No payment <{payment_id}> was found", status=404))
    if payment.status in (PaymentStatus.approved, PaymentStatus.cancelled):
        abort(Response(f"Can't update payment in state <{payment.status}>", status=409))
    if not payload:
        abort(Response("No payment data was provided", status=400))

    messages = []
    payment.when_changed = datetime.now()
    payment.changed_by = current_user
    if payload.get('amount_original'):
        payment.amount_sent_original = payload['amount_original']
    if payload.get('currency_code'):
        payment.currency = Currency.query.get(payload['currency_code'])
    if payload.get('amount_krw'):
        payment.amount_sent_krw = payload['amount_krw']
    if payload.get('amount_received_krw'):
        payment.amount_received_krw = payload['amount_received_krw']
    if payload.get('status'):
        try:
            payment.set_status(payload['status'].lower(), messages)
        except PaymentNoReceivedAmountException as ex:
            abort(Response(str(ex), status=409))

    db.session.commit()

    return jsonify({'payment': payment.to_dict(), 'message': messages})

@bp_api_user.route('', defaults={'payment_id': None})
@bp_api_user.route('/<int:payment_id>')
@login_required
def user_get_payments(payment_id):
    '''
    Returns user's or all payments in JSON
    '''
    payments = Payment.query
    if not current_user.has_role('admin'):
        payments = payments.filter_by(user=current_user)
    if payment_id is not None:
        payment = payment.filter_by(id=payment_id)
    if request.values.get('order_id'):
        payments = payments.filter(
            Payment.orders.any(Order.id == request.values['order_id']))

    return jsonify(list(map(lambda tran: tran.to_dict(), payments)))

@bp_api_user.route('', methods=['POST'])
@login_required
def user_create_payment():
    payload = request.get_json()
    if not payload:
        abort(Response('No payment data was provided', status=400))
    currency = Currency.query.get(payload['currency_code'])
    if not currency:
        abort(Response(f"No currency <{payload['currency_code']}> was found", status=400))

    payment = Payment(
        user=current_user,
        changed_by=current_user,
        orders=Order.query.filter(Order.id.in_(payload['orders'])).all(),
        currency=currency,
        amount_sent_original=payload['amount_original'],
        amount_sent_krw=float(payload['amount_original']) / float(currency.rate),
        payment_method_id=payload['payment_method'],
        status=PaymentStatus.pending,
        when_created=datetime.now()
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify(payment.to_dict())

@bp_api_user.route('/<int:payment_id>', methods=['POST'])
@login_required
def user_save_payment(payment_id):
    '''
    Saves updates in payment
    '''
    payload = request.get_json()
    payment = Payment.query.get(payment_id)
    if not payment:
        abort(404)

    if payment.status in (PaymentStatus.approved, PaymentStatus.cancelled):
        abort(Response(
            f"Can't update payment in state <{payment.status}>", status=409))
    if payload['status'] == 'cancelled':
        payment.status = PaymentStatus.cancelled

    payment.when_changed = datetime.now()
    payment.changed_by = current_user

    db.session.commit()

    return jsonify(payment.to_dict())

@bp_api_user.route('/<int:payment_id>/evidence', methods=['POST'])
@login_required
def user_upload_payment_evidence(payment_id):
    payment = Payment.query.get(payment_id)
    if not current_user.has_role('admin') and \
        current_user != payment.user:
        abort(403)
    if payment.status in (PaymentStatus.approved, PaymentStatus.cancelled):
        abort(Response(
            f"Can't update payment in state <{payment.status}>", status=409))
    if request.files and request.files['file'] and request.files['file'].filename:
        file = request.files['file']
        rm(payment.proof_image)
        image_data = file.read()
        file_name = os.path.join(
            current_app.config['UPLOAD_PATH'],
            str(current_user.id),
            datetime.now().strftime('%Y-%m-%d.%H%M%S.%f')) + \
            ''.join(os.path.splitext(file.filename)[1:])
        write_to_file(file_name, image_data)
    
        payment.proof_image = file_name
        payment.when_changed = datetime.now()
        payment.changed_by = current_user
        db.session.commit()
    else:
        abort(Response("No file is uploaded", status=400))
    return jsonify({})

@bp_api_user.route('/method')
@login_required
def get_payment_methods():
    payment_methods = PaymentMethod.query
    return jsonify(list(map(lambda pm: pm.to_dict(), payment_methods)))