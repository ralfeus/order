'''
Contains API endpoint routes of the payment services
'''
from datetime import datetime
from hashlib import md5
import os, os.path

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.payments import bp_api_admin, bp_api_user
from app.currencies.models.currency import Currency
from app.orders.models.order import Order
from app.payments.models.payment import Payment, PaymentStatus
from app.payments.models.payment_method import PaymentMethod
from app.models.user import User

from app.exceptions import PaymentNoReceivedAmountException
from app.tools import get_tmp_file_by_id, modify_object, rm, write_to_file

@bp_api_admin.route('', defaults={'payment_id': None})
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
    if isinstance(payload['amount_original'], str):
        payload['amount_original'] = payload['amount_original'].replace(',', '.')
    currency = Currency.query.get(payload['currency_code'])
    if not currency:
        abort(Response(f"No currency <{payload['currency_code']}> was found", status=400))
    user = current_user
    if current_user.has_role('admin') and payload.get('user_id'):
        user = User.query.get(payload['user_id'])
        if user is None:
            abort(Response(f"No user <{payload['user_id']}> was found", status=400))

    evidence_file = None
    if payload.get('evidences') and len(payload['evidences']) > 0:
        evidence_src_file = get_tmp_file_by_id(payload['evidences'][0][0])
        evidence_file = f"{current_app.config['UPLOAD_PATH']}/{os.path.basename(evidence_src_file)}"
        os.rename(evidence_src_file, os.path.abspath(evidence_file))

    payment = Payment(
        user=user,
        changed_by=current_user,
        orders=Order.query.filter(Order.id.in_(payload['orders'])).all(),
        currency=currency,
        amount_sent_original=payload.get('amount_original'),
        amount_sent_krw=float(payload.get('amount_original')) / float(currency.rate),
        payment_method_id=payload.get('payment_method'),
        additional_info=payload.get('additional_info'),
        evidence_image=evidence_file,
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


def _upload_payment_evidence():
    if not request.files or len(request.files) == 0:
        return

    session_id = md5(request.cookies[current_app.session_cookie_name].encode()).hexdigest()
    file_num = 0
    file_ids = []
    for uploaded_file in request.files.items():
        file_id = f'{session_id}-{file_num}'
        file_name = "/tmp/payment-evidence-{}{}".format(
            file_id,
            os.path.splitext(uploaded_file[1].filename)[1])
        uploaded_file[1].save(dst=file_name)
        file_ids.append(file_id)
        file_num += 1
    return file_ids

@bp_api_user.route('/evidence', defaults={'payment_id': None}, methods=['POST'])
@bp_api_user.route('/<int:payment_id>/evidence', methods=['POST'])
@login_required
def user_upload_payment_evidence(payment_id):
    if payment_id is None:
        file_ids = _upload_payment_evidence()
        return jsonify({
            'upload': {
                'id': file_ids
            }
        })

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

@bp_api_admin.route('/method/<payment_method_id>', methods=['POST'])
@bp_api_admin.route('/method', methods=['POST'], defaults={'payment_method_id': None})
@roles_required('admin')
def save_payment_method(payment_method_id):
    payment_method = PaymentMethod.query.get(payment_method_id)
    if payment_method_id:
        if not payment_method:
            abort(Response(f"Payment method <{payment_method_id}> wasn't found", status=404))
    else:
        payment_method = PaymentMethod()
        db.session.add(payment_method)
    payload = request.get_json()
    if not payload:
        abort(Response("No payment method details are provided", status=400))
    modify_object(payment_method, payload, ['name', 'payee_id', 'instructions'])
    db.session.commit()
    return jsonify({'data': [payment_method.to_dict()]})

@bp_api_admin.route('/method/<payment_method_id>', methods=['DELETE'])
@roles_required('admin')
def delete_payment_method(payment_method_id):
    payment_method = PaymentMethod.query.get(payment_method_id)
    if not payment_method:
        abort(Response(f"Payment method <{payment_method_id}> wasn't found", status=404))
    try:
        db.session.delete(payment_method)
        db.session.commit()
        return jsonify({'status': 'success'})
    except:
        abort(Response("Can't delete the payment method <{payment_method}> as it's used",
              status=409))

@bp_api_user.route('/status')
@login_required
def user_get_payment_statuses():
    return jsonify(list(map(lambda i: i.name, PaymentStatus)))
