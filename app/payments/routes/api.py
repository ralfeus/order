'''
Contains API endpoint routes of the payment services
'''
from app.payments.validators.payment import PaymentValidator
from datetime import datetime
from hashlib import md5
import os, os.path
import shutil
from tempfile import NamedTemporaryFile


from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required
from sqlalchemy import not_

from app import db
from app.payments import bp_api_admin, bp_api_user
from app.currencies.models.currency import Currency
from app.orders.models.order import Order
from app.payments.models.payment import Payment, PaymentStatus
from app.payments.models.payment_method import PaymentMethod
from app.models.file import File
from app.users.models.user import User

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

    return jsonify([entry.to_dict() for entry in payments])

@bp_api_admin.route('/<int:payment_id>', methods=['POST'])
@roles_required('admin')
def admin_save_payment(payment_id):
    ''' Saves updates of user payment '''
    payload = request.get_json()
    payment = Payment.query.get(payment_id)
    if not payment:
        abort(Response(f"No payment <{payment_id}> was found", status=404))
    if not payment.is_editable():
        abort(Response(f"Can't update payment in state <{payment.status}>", status=409))
    if not payload:
        abort(Response("No payment data was provided", status=400))

    messages = []
    payment.when_changed = datetime.now()
    payment.changed_by = current_user
    if payload.get('amount_sent_original'):
        payment.amount_sent_original = payload['amount_sent_original']
    if payload.get('currency_code'):
        payment.currency = Currency.query.get(payload['currency_code'])
    if payload.get('amount_sent_krw'):
        payment.amount_sent_krw = payload['amount_sent_krw']
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
        payments = payments.filter_by(id=payment_id)
    if request.values.get('order_id'):
        payments = payments.filter(
            Payment.orders.any(Order.id == request.values['order_id']))

    return jsonify([tran.to_dict() for tran in payments])

@bp_api_user.route('', methods=['POST'])
@login_required
def user_create_payment():
    user = None
    payload = request.get_json()
    if not current_user.has_role('admin') or 'user_id' not in request.json.keys():
        request.json['user_id'] = current_user.id
        user = current_user
    elif int(payload['user_id']) == current_user.id:
        user = current_user
    else:
        user = User.query.get(payload['user_id'])
    with PaymentValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't create a Payment",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    if isinstance(payload['amount_sent_original'], str):
        payload['amount_sent_original'] = payload['amount_sent_original'].replace(',', '.')
    currency = Currency.query.get(payload['currency_code'])
    if not currency:
        abort(Response(f"No currency <{payload['currency_code']}> was found", status=400))
    evidences = []
    if payload.get('evidences'):
        for evidence in payload['evidences']:
            evidences.append(File(
                file_name=evidence['file_name'],
                path=_move_uploaded_file(evidence['id'])
            ))

    payment = Payment(
        user=user,
        changed_by=current_user,
        orders=Order.query.filter(Order.id.in_(payload['orders'])).all(),
        currency=currency,
        amount_sent_original=payload.get('amount_sent_original'),
        amount_sent_krw=float(payload.get('amount_sent_original')) / float(currency.rate),
        payment_method_id=payload.get('payment_method').get('id'),
        additional_info=payload.get('additional_info'),
        evidences=evidences,
        status=PaymentStatus.pending,
        when_created=datetime.now()
    )

    db.session.add(payment)
    db.session.commit()
    return jsonify({'data': [payment.to_dict()]})

@bp_api_user.route('/<payment_id>', methods=['DELETE'])
@login_required
def user_delete_payment(payment_id):
    ''' Cancels payment request '''
    payment = Payment.query.get(payment_id)
    if payment is None:
        abort(404)
    if not payment.is_editable():
        return jsonify({
            'error': f"Can't cancel payment in state [{payment.status}]"
        })
    payment.status = PaymentStatus.cancelled
    db.session.commit()
    return jsonify({})

def _move_uploaded_file(file_id):
    evidence_src_file = get_tmp_file_by_id(file_id)
    evidence_file = f"{current_app.config['UPLOAD_PATH']}/{os.path.basename(evidence_src_file)}"
    shutil.move(evidence_src_file, os.path.abspath(evidence_file))
    return evidence_file

# @bp_api_user.route('/<int:payment_id>', methods=['POST'])
@login_required
def user_save_payment(payment_id):
    '''Saves updates in payment'''
    payment = Payment.query.get(payment_id)
    if not payment:
        abort(404)
    if not payment.is_editable():
        abort(Response(
            f"Can't update payment in state <{payment.status}>", status=409))
    with PaymentValidator(request) as validator:
        if not validator.validate():
            abort(jsonify(validator.errors))
        # return jsonify({
        #     'id': payment_id,
        #     'data': [payment.to_dict()],
        #     'cancelled': [payment_id],
        #     'error': "Couldn't update a Payment",
        #     'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
        #                     for message in payload.errors]
        # })
    payload = request.get_json()
    if current_user.has_role('admin'):
        modify_object(payment, payload,
            ['additional_info', 'amount_sent_krw', 'amount_sent_original', 'amount_received_krw',
            'currency_code', 'status', 'user_id'])
        if payload.get('payment_method') \
            and payment.payment_method_id != payload['payment_method']['id']:
            payment.payment_method_id = payload['payment_method']['id']
            payment.when_changed = datetime.now()
        evidences = {e.path: e for e in payment.evidences}
        payment.evidences = []
        for evidence in payload.get('evidences'):
            if evidence.get('id'):
                payment.evidences.append(File(
                    file_name=evidence['file_name'],
                    path=_move_uploaded_file(evidence['id'])
                ))
            elif evidence.get('path'):
                payment.evidences.append(evidences[evidence['path']])
        # removed_evidences = payment.evidences.filter(
        #     File.path.notin_(remaining_evidences))
        # for evidence in removed_evidences:
        #     payment.evidences.filter_by(id=evidence.id).delete()
        #     db.session.delete(evidence)
        if payload.get('orders'):
            payment.orders = Order.query.filter(Order.id.in_(payload['orders']))
    else:
        modify_object(payment, payload, ['status'])

    payment.changed_by = current_user
    db.session.commit()
    return jsonify({'data': [payment.to_dict()]})


def _upload_payment_evidence():
    if not request.files or len(request.files) == 0:
        return

    file_ids = []
    file_names = {}
    for uploaded_file in request.files.items():
        # file_id = None
        file = NamedTemporaryFile()
        # file_id = f'{session_id}-{file_num}'
        file_name = file.name + os.path.splitext(uploaded_file[1].filename)[1]
        file_id = os.path.basename(file.name)
        uploaded_file[1].save(dst=file_name)
        file_ids.append(file_id)
        file_names[file_id] = {'filename': uploaded_file[1].filename}
    return file_ids, file_names

@bp_api_user.route('/evidence', defaults={'payment_id': None}, methods=['POST'])
@bp_api_user.route('/<int:payment_id>/evidence', methods=['POST'])
@login_required
def user_upload_payment_evidence(payment_id):
    if payment_id is None:
        file_ids, file_names = _upload_payment_evidence()
        return jsonify({
            'upload': {
                'id': file_ids,
            },
            'files': {
                'files': file_names
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
        current_app.logger.warning("Payment %s upload evidence: no file was uploaded", payment_id)
        current_app.logger.warning(request.files)
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
