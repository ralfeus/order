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
    payee_name = Setting.query.get('payment.paypal.payee_address').value
    return render_template('payment_methods/paypal.html',
        client_id=paypal_client_id,
        payee_name=payee_name,
        payment=payment
    )

@bp_api_user.route('/paypal/complete', methods=['POST'])
def paypal_callback():
    logger = logging.getLogger('paypal_callback')
    payload = request.get_json()
    # logger.info(request.get_json())
    event_type = payload['event_type']
    if event_type == 'CHECKOUT.ORDER.APPROVED':
        payment_data = payload['resource']['purchase_units'][0]
        payment_id = payment_data['reference_id']
        capture = payment_data['payments']['captures'][0]
        if capture['status'] != 'COMPLETED':
            logger.info("Payment %s is yet pending. Ignoring...", payment_id)
            return jsonify(payload), 202
        logger.info("Got PayPal completion for payment %s", payment_id)
        from app.currencies.models.currency import Currency
        from app.payments.models.payment import Payment
        from app import db
        payment = Payment.query.get(payment_id)
        if payment is None:
            logger.warning('No payment %s was found', payment_id)
            return jsonify(payload), 202
        if payment.status == PaymentStatus.approved:
            logger.info("The payment %s is already approved. Ignoring...", payment_id)
            return jsonify(payload), 202
        try:
            net_amount = \
                payment_data['payments']['captures'][0]['seller_receivable_breakdown']['net_amount']
        except KeyError:
            logger.exception(payload)
            return jsonify(payload), 202
        received_currency = Currency.query.get(net_amount['currency_code'])
        if received_currency is None:
            logger.info("Unknown currency is received %s", net_amount['currency_code'])
            return jsonify(payload), 202
        net_amount = int(float(net_amount['value']) / float(received_currency.get_rate()))
        payment.amount_received_krw = net_amount
        payment.set_status(PaymentStatus.approved)
        db.session.commit()
    else:
        logger.debug(event_type)
    return jsonify(payload), 202
