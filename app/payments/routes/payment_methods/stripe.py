from datetime import datetime
from decimal import Decimal
import json
import logging
import math
from flask import current_app, jsonify, redirect, request, url_for
import stripe
import requests
from app import db, cache
from app.currencies.models.currency import Currency
from app.payments import bp_api_user, bp_client_user
from app.payments.logging import get_logger
from app.payments.models.payment import Payment, PaymentStatus
from app.models.file import File
from app.tools import write_to_file
log = get_logger()

class FeeStructure:
    send_to_stripe = 0.0 # Step 1
    stripe_fee = 0 # Step 2
    service_fee = 0 # Step 3
    send_to_wise = 0 # Step 4
    stripe_wise_fee = 0 # Step 5
    send_to_bank = 0 # Step 6
    wise_fee = 0 # Step 7

    total_service_fee = 0

    def __init__(self, **kwargs):
        for attr in dir(self):
            if not (attr.startswith('__') or callable(getattr(self, attr))):
                setattr(self, attr, kwargs.get(attr, 0))

    def to_dict(self):
        return {
            attr: getattr(self, attr) for attr in dir(self)
                if not (attr.startswith('__') or callable(getattr(self, attr)))
        }
    
    def __str__(self):
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, json):
        return cls(**{
            attr: json.get(attr, 0) for attr in cls.__dict__
        })
    


class ExchangeRateManager:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
    
    def get_rate(self, base, target) -> float:
        """
        Get current exchange rate from Frankfurter API (free, no auth required)
        Returns float rate or None on error
        """
        cache_key = f"{current_app.config.get('TENANT_NAME', 'default')}_{base}_{target}"
        
        # Return cached if fresh (< 5 minutes)
        if cache.has(cache_key):
            rate = cache.get(cache_key)
            log.debug(f"Got {cache_key} rate {rate} from the cache")
            return rate
        
        try:
            from lxml.cssselect import CSSSelector
            from lxml import etree #type: ignore
            # Now it's specific for Kookmin bank of Korea
            # url = f'https://api.frankfurter.app/latest?from={base}&to={target}'
            date = datetime.now().strftime('%Y%m%d')
            url = 'https://omoney.kbstar.com/quics?chgCompId=b104602&baseCompId=b104602&page=C102554&cc=b104602:b104602'
            data= f'%EB%93%B1%EB%A1%9D%ED%9A%8C%EC%B0%A8=1083&searchDate={date}'
            response = requests.post(url, data, timeout=5)
            response.raise_for_status()

            rate = 0
            doc = etree.fromstring(response.content.decode(), parser=etree.HTMLParser())
            rows = CSSSelector('#inqueryTable table tbody tr')(doc)
            for row in rows:
                cols = row.cssselect('td')
                currency = etree.tostring(cols[0], method='text', encoding='unicode').strip()
                if currency == target:
                    rate = 1 / float(cols[4].text.strip().replace(',',''))
                    break
            if rate == 0:
                raise Exception("Couldn't find target rate")
            # data = response.json()
            # rate = data['rates'][target]
            log.debug(f"Got {cache_key} rate {rate} from Kookmin")
            # Cache it
            cache.set(cache_key, rate, timeout=600)
            
            return rate
            
        except requests.exceptions.RequestException as e:
            log.warning(f"Error fetching {base}/{target} rate: {e}")
            raise

# Fee configuration
FEES = {
    'EUR': {'total': 0.05, 'stripe_wise': 0.0,  'swift': 0.005, 'service': 0.02},
    'USD': {'total': 0.06, 'stripe_wise': 0.01, 'swift': 0.005, 'service': 0.02},
}

def calculate_base_amount(payment: Payment) -> float:
    log.set_payment_id(payment.id)
    om_rate = Currency.query.get(payment.currency_code).rate
    fx_rate = om_rate
    try:
        fx_rate = ExchangeRateManager().get_rate(
            Currency.get_base_currency(current_app.config['TENANT_NAME']).code, 
            payment.currency_code)
    except:
        pass # Just use same rate as in a system
    log.info(f"Original amount in {payment.currency_code}: {payment.amount_sent_original}")
    log.info(f"Site's {payment.currency_code} rate: {om_rate}")
    log.info(f"Bank's {payment.currency_code} rate: {fx_rate}")
    fx_rate *= 1.01
    log.info(f"Bank's {payment.currency_code} currency risk compensated rate: {fx_rate}")
    adjustment_quoefficient = Decimal(fx_rate) / om_rate
    log.info(f"Original amount adjustment quoefficient: {adjustment_quoefficient}")
    adjusted_amount = math.ceil(float(payment.amount_sent_original * adjustment_quoefficient) * 100) / 100
    log.info(f"Adjusted base amount: {adjusted_amount}")
    return adjusted_amount

def calculate_service_fee(base_amount, currency) -> FeeStructure:
    """Calculate service fee based on currency"""
    fee_config = FEES[currency]

    f = FeeStructure()
    f.send_to_bank = math.ceil(base_amount / (1 - fee_config['swift']) * 100) / 100
    f.wise_fee = f.send_to_bank - base_amount
    f.send_to_wise = math.ceil(f.send_to_bank / (1 - fee_config['stripe_wise']) * 100) / 100
    f.stripe_wise_fee = math.ceil((f.send_to_wise - f.send_to_bank) * 100) / 100
    f.service_fee = math.ceil(base_amount * fee_config['service'] * 100) / 100
    f.send_to_stripe = math.ceil(base_amount * (1 + fee_config['total']) * 100) / 100
    f.stripe_fee = f.send_to_stripe - f.send_to_wise - f.service_fee

    f.total_service_fee = f.send_to_stripe - base_amount
    log.info(f"Fees structure: {f}")
    return f

def find_or_create_customer(payment: Payment) -> str:
    """
    Find existing customer by email, create if not found
    """
    email = payment.orders[0].email \
        if payment.orders.count() and payment.orders[0].email else None
    name = payment.sender_name or f"Payer {payment.id}"
    if email:
        # Search for existing customer by email
        customers = stripe.Customer.search(
            query=f"email:'{email}'",
            limit=1
        )
    elif name:
        # Search for existing customer by name (not ideal, but fallback if email is not provided)
        customers = stripe.Customer.search(
            query=f"name:'{name}'",
            limit=1
        )
        
    if not customers.is_empty:
        logging.info(f"Found existing customer: {customers.data[0].id}")
        return customers.data[0].id
    
    # No existing customer found, create new
    logging.info("Creating new customer")
    customer = stripe.Customer.create(
        name=name,
        email=email or '',
        metadata={"created_via": "payment_processor"}
    )
    return customer.id

@bp_client_user.route('/<int:payment_id>/stripe/checkout')
def checkout(payment_id):
    """Create Stripe Checkout Session and redirect to it"""
    log.set_payment_id(payment_id)
    payment = Payment.query.get(payment_id)
    if not payment:
        return "Payment not found", 404

    if not payment.currency or not payment.currency.enabled or payment.currency_code not in FEES.keys():
        return \
            f"Unsupported currency {payment.currency.name}. " \
            f"If you wish to pay with Stripe in {payment.currency.name}, " \
            f"please contact administrator", 400

    stripe.api_key = current_app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')

    base_amount = calculate_base_amount(payment)
    fees = calculate_service_fee(base_amount, payment.currency_code)
    total_amount = max(fees.send_to_stripe, float(payment.amount_sent_original))

    zero_decimal_currencies = {
        'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA', 'PYG',
        'RWF', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'
    }
    is_zero_decimal = payment.currency_code.upper() in zero_decimal_currencies
    unit_amount = int(total_amount) if is_zero_decimal else int(total_amount * 100)

    customer_id = find_or_create_customer(payment)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode='payment',
        line_items=[{
            'price_data': {
                'currency': payment.currency_code.lower(),
                'product_data': {'name': f'Payment #{payment.id}'},
                'unit_amount': unit_amount,
            },
            'quantity': 1,
        }],
        payment_intent_data={
            'metadata': {
                'payment_id': str(payment.id),
                'base_amount': str(payment.amount_sent_original),
                'base_amount_fx_rate_compensated': str(base_amount),
                'service_fee': str(fees.service_fee),
                'send_to_wise': str(fees.send_to_wise),
                'send_to_bank': str(fees.send_to_bank),
            },
        },
        success_url=url_for('.success', payment_id=payment.id, _external=True),
        cancel_url=url_for('.cancel', payment_id=payment.id, _external=True),
    )
    if not session.url:
        return "Failed to create Stripe Checkout session", 500
    return redirect(session.url)

@bp_client_user.route('/<int:payment_id>/stripe/success')
def success(payment_id: int):
    """Stripe redirects here after successful checkout. Approval is handled by webhook."""
    log.set_payment_id(payment_id)
    log.info(f"Stripe checkout success redirect for payment {payment_id}")
    return redirect(url_for('.user_wallet', result='success'))

@bp_client_user.route('/<int:payment_id>/stripe/cancel')
def cancel(payment_id: int):
    """Stripe redirects here when the user cancels checkout."""
    log.set_payment_id(payment_id)
    log.info(f"Stripe checkout cancelled for payment {payment_id}")
    return redirect(url_for('.user_wallet', result='failed',
                            message='Payment was not completed. No funds were charged. Please create a new payment.'))

@bp_api_user.route('/stripe/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('PAYMENT', {}).get('stripe', {}).get('webhook_secret')
    stripe.api_key = current_app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')

    try:
        log.info("Constructing Stripe webhook event")
        # log.debug(f"Payload: {payload}")
        # log.debug(f"Webhook secret: {webhook_secret}")
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        log.error("Invalid payload in Stripe webhook")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError: #type: ignore
        log.error("Invalid signature in Stripe webhook")
        return jsonify({'error': 'Invalid signature'}), 400

    if event.type == 'checkout.session.completed':
        _handle_checkout_complete(event.data.object)

    return jsonify({'status': 'ok'})

def _handle_checkout_complete(session):
    """Approve payment and save receipt after successful Stripe Checkout."""
    try:
        intent = stripe.PaymentIntent.retrieve(session.payment_intent, expand=['latest_charge'])
    except Exception as e:
        log.warning(f"Failed to retrieve PaymentIntent {session.payment_intent}: {e}")
        return

    payment_id_str = intent.metadata.get('payment_id', '')
    if not payment_id_str.isnumeric():
        log.warning(f"Invalid payment_id in Stripe PaymentIntent metadata: {payment_id_str!r}")
        return
    payment_id = int(payment_id_str)
    log.set_payment_id(payment_id)

    payment: Payment = Payment.query.get(payment_id)
    if not payment:
        log.warning(f"Payment {payment_id} not found")
        return
    if payment.status != PaymentStatus.pending:
        log.info(f"Payment {payment_id} is already in status {payment.status}, skipping")
        return

    log.info(f"Approving payment {payment_id}")
    payment.amount_received_krw = payment.amount_sent_krw
    payment.set_status(PaymentStatus.approved)
    db.session.commit() #type: ignore

    try:
        charge = intent.latest_charge
        if charge and hasattr(charge, 'receipt_url') and charge.receipt_url: #type: ignore
            response = requests.get(charge.receipt_url) #type: ignore
            if response.status_code == 200:
                filename = f"{session.payment_intent}.html"
                upload_path = current_app.config.get('UPLOAD_PATH', 'upload')
                path = f"{upload_path}/{filename}"
                write_to_file(path, response.content)
                file_obj = File(file_name=filename, path=path)
                payment.evidences.append(file_obj)
                db.session.add(file_obj) #type: ignore
                db.session.commit() #type: ignore
    except Exception as e:
        log.warning(f"Failed to save receipt for payment {payment_id}: {e}")
