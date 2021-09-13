'''PayPal checkout page'''
from app.payments.models.payment import PaymentStatus
import logging

from flask import abort, jsonify, render_template, request
from flask_security import login_required
from app.payments import bp_api_user, bp_client_user

@bp_client_user.route('/<int:payment_id>/paypal')
@login_required
def get_paypal_checkout(payment_id):
    from app.payments.models.payment import Payment
    from app.settings.models.setting import Setting
    payment = Payment.query.get(payment_id)
    if payment is None:
        abort(404)
    paypal_client_id = Setting.query.get('payment.paypal.client_id').value
    return render_template('payment_methods/paypal.html',
        client_id=paypal_client_id,
        payment=payment
    )

@bp_api_user.route('/paypal/complete', methods=['POST'])
def paypal_callback():
    logger = logging.getLogger('paypal_callback')
    payload = request.get_json()
    # logger.info(request.get_json())
    event_type = payload['event_type']
    if event_type == 'CHECKOUT.ORDER.APPROVED':
        payment_id = payload['resource']['purchase_units'][0]['reference_id']
        logger.info("Got PayPal approval for payment %s", payment_id)
        from app.payments.models.payment import Payment
        from app import db
        payment = Payment.query.get(payment_id)
        if payment is None:
            logger.warning('No payment %s was found', payment_id)
            return jsonify({})
        payment.status = PaymentStatus.approved
        db.session.commit()
    return jsonify({})
