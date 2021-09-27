'''PayPal checkout page'''
from app.payments.models.payment import PaymentStatus
import logging

from flask import abort, current_app, jsonify, render_template, request
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

@bp_api_user.route('<int:payment_id>/paypal/create', methods=['POST'])
@login_required
def user_create_paypal_order(payment_id):
    from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
    from paypalcheckoutsdk.orders import OrdersCreateRequest
    from app.payments.models.payment import Payment
    from app.settings.models.setting import Setting
    payment = Payment.query.get(payment_id)
    if payment is None:
        abort(404)
    client_id = Setting.get('payment.paypal.client_id')
    client_secret = Setting.get('payment.paypal.client_secret')
    assert client_id and client_secret
    environment = SandboxEnvironment(client_id=client_id, client_secret=client_secret) \
        if current_app.env == 'development' \
            else LiveEnvironment(client_id=client_id, client_secret=client_secret)
    paypal_client = PayPalHttpClient(environment)
    order_request = OrdersCreateRequest()
    order_request.prefer('return=representation')
    order_request.request_body({
        'intent': 'CAPTURE',
        'purchase_units': [{
            'amount': {
              'currency_code': "RUB" if payment.currency_code == "RUR" else payment.currency_code,
              'value': float(payment.amount_sent_original)
            },
            'reference_id': payment.id
        }]
    })
    response = paypal_client.execute(order_request)
    return jsonify(response.result.dict()), 201

@bp_api_user.route('/paypal/capture', methods=['POST'])
def user_capture_paypal_order():
    logger = logging.getLogger('user_capture_paypal_order')
    from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
    from paypalcheckoutsdk.orders import OrdersCaptureRequest
    from paypalhttp import HttpError
    from app.settings.models.setting import Setting
    client_id = Setting.get('payment.paypal.client_id')
    client_secret = Setting.get('payment.paypal.client_secret')
    assert client_id and client_secret
    environment = SandboxEnvironment(client_id=client_id, client_secret=client_secret) \
        if current_app.env == 'development' \
            else LiveEnvironment(client_id=client_id, client_secret=client_secret)
    paypal_client = PayPalHttpClient(environment)
    capture_request = OrdersCaptureRequest(request.args['order_id'])
    try:
        result = paypal_client.execute(capture_request).result
        if result.status == 'COMPLETED':
            approve_payment(result)
        return jsonify(result.dict()), 201
    except IOError as ioe:
        if isinstance(ioe, HttpError):
            # Something went wrong server-side
            logger.error(ioe.status_code)
            logger.error(ioe.headers)
        logger.error(ioe)

def approve_payment(capture_result):
    logger = logging.getLogger('approve_payment')
    payment_data = capture_result.purchase_units[0]
    payment_id = payment_data.reference_id
    from app import db
    from app.currencies.models.currency import Currency
    from app.payments.models.payment import Payment
    payment = Payment.query.get(payment_id)
    if payment is None:
        logger.warning('No payment %s was found', payment_id)
        return
    if payment.status == PaymentStatus.approved:
        logger.info("The payment %s is already approved. Ignoring...", payment_id)
        return
    net_amount = \
        payment_data.payments.captures[0].seller_receivable_breakdown.net_amount
    received_currency = Currency.query.get(net_amount.currency_code)
    if received_currency is None:
        logger.info("Unknown currency is received %s", net_amount.currency_code)
        return
    net_amount = int(float(net_amount.value) / float(received_currency.get_rate()))
    payment.amount_received_krw = net_amount
    payment.set_status(PaymentStatus.approved)
    db.session.commit()
   