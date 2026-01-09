# stripe_custom.py (or add to your existing stripe.py)

import logging
from typing import Any
from flask import request, jsonify, render_template
import stripe
import requests
from app import app, db
from app.payments import bp_api_user, bp_client_user
from app.payments.models.payment import Payment, PaymentStatus
from app.models.file import File
from app.tools import write_to_file
from exceptions import PaymentError

class FeeStructure:
    send_to_stripe = 0 # Step 1
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
    
    @classmethod
    def from_dict(cls, json):
        return cls(**{
            attr: json.get(attr, 0) for attr in cls.__dict__
        })

# Fee configuration (same as before)
FEES = {
    'USD': {
        'domestic': {'percentage': 0.015, 'fixed': 0.31},
        'international': {'percentage': 0.0325, 'fixed': 0.31},
        'stripe-wise': 0.005,
        'swift': 0.005,
        'service': 0.02
    },
    'EUR': {
        'domestic': {'percentage': 0.015, 'fixed': 0.26},
        'international': {'percentage': 0.0325, 'fixed': 0.26},
        'stripe-wise': 0,
        'swift': 0.005,
        'service': 0.02
    },
}

EEA_COUNTRIES = {
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'IS', 'LI', 'NO'
}

def calculate_service_fee(base_amount, card_country, currency):
    """Calculate service fee based on card country"""
    is_domestic = card_country.upper() in EEA_COUNTRIES
    stripe_fee = 'domestic' if is_domestic else 'international'
    fee_config = FEES[currency]
    
    f = FeeStructure()
    f.send_to_bank = base_amount / (1 - fee_config['swift'])
    f.wise_fee = f.send_to_bank - base_amount
    f.send_to_wise = f.send_to_bank / (1 - fee_config['stripe-wise'])
    f.stripe_wise_fee = f.send_to_wise - f.send_to_bank
    f.service_fee = base_amount * fee_config['service']
    at_stripe = f.send_to_wise + f.service_fee
    f.send_to_stripe = at_stripe / (1 - fee_config[stripe_fee]['percentage']) + fee_config[stripe_fee]['fixed']
    f.stripe_fee = f.send_to_stripe * fee_config[stripe_fee]['percentage'] + fee_config[stripe_fee]['fixed']
    
    f.total_service_fee = f.wise_fee + f.stripe_wise_fee + f.service_fee + f.stripe_fee
    
    return {
        'total_service_fee': round(f.total_service_fee, 2),
        'is_domestic': is_domestic,
        'card_type': 'EEA Card' if is_domestic else 'International Card',
        'breakdown': f
    }

@bp_client_user.route('/<int:payment_id>/stripe/checkout')
def checkout(payment_id):
    """Render custom checkout page"""
    # Load payment from database
    payment = Payment.query.get(payment_id)
    if not payment:
        return "Payment not found", 404

    # Verify supported currency
    if not payment.currency or not payment.currency.enabled or payment.currency_code not in FEES.keys():
        return \
            f"Unsupported currency {payment.currency.name}. " \
            f"If you wish to pay with Stripe in {payment.currency.name}, " \
            f"please contact administrator", 400

    return render_template('payment_methods/stripe.html',
                          payment=payment,
                          stripe_key=app.config.get('PAYMENT', {}).get('stripe', {}).get('api_key'),
                          stripe_payment_key=app.config.get('PAYMENT', {}).get('stripe', {}).get('api_payment_key'))

@bp_client_user.route('<int:payment_id>/stripe/success')
def success(payment_id: int):
    """Handle Stripe payment success redirect"""
    try:
        # Get payment_intent from query parameters
        payment_intent_id = request.args.get('payment_intent')
        if not payment_intent_id:
            logging.warning("No payment intent ID is provided")
            return render_template('payment_methods/stripe_success.html', success=False)

        # Configure Stripe
        stripe.api_key = app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')

        # Retrieve PaymentIntent from Stripe to verify status
        intent = stripe.PaymentIntent.retrieve(payment_intent_id, 
                                               expand=['latest_charge'])

        # Verify payment is successful using Stripe's data
        if intent.status != 'succeeded':
            logging.info(f"Payment status is '{intent.status}'")
            return render_template('payment_methods/stripe_success.html', success=False)

        # Get payment_id from metadata
        payment_id_from_stripe = int(intent.metadata.get('payment_id', '0')) \
            if intent.metadata.get('payment_id', '0').isnumeric() else 0
        if payment_id != payment_id_from_stripe:
            logging.info(f"The payment ID doesn't match ({payment_id} is provided, "
                         f"{payment_id_from_stripe} is in Stripe payment)")
            return render_template('payment_methods/stripe_success.html', success=False)

        # Find payment entity
        payment = Payment.query.get(int(payment_id))
        if not payment:
            logging.info(f"No payment ID {payment_id} was found")
            return render_template('payment_methods/stripe_success.html', success=False)

        # Change payment status to approved
        logging.info(f"Approving payment {payment_id}")
        payment.amount_received_krw = payment.amount_sent_krw
        payment.set_status(PaymentStatus.approved)
        db.session.commit()  # type: ignore

        # Download and save receipt
        try:
            if intent.latest_charge and hasattr(intent.latest_charge, 'receipt_url') \
                and intent.latest_charge.receipt_url: #type: ignore
                response = requests.get(intent.latest_charge.receipt_url) #type: ignore
                if response.status_code == 200:
                    filename = f"{intent.id}.html"
                    upload_path = app.config.get('UPLOAD_PATH', 'upload')
                    path = f"/{upload_path}/{filename}"
                    write_to_file(path, response.content)
                    file_obj = File(file_name=filename, path=path[1:])
                    payment.evidences.append(file_obj)
                    db.session.add(file_obj) #type: ignore
                    db.session.commit() #type: ignore
        except Exception as e:
            logging.warning(f"Failed to download and save receipt for payment {payment_id}: {e}")

        # Return success template
        return render_template('payment_methods/stripe_success.html', success=True)

    except Exception as e:
        # Log error but still close window to avoid confusion
        logging.exception(f"Error in Stripe success handler: {e}")
        return render_template('payment_methods/stripe_success.html', success=False)

@bp_api_user.route('/stripe/detect-card', methods=['POST'])
def detect_card():
    """Detect card country from payment method"""
    try:
        data: dict[str, Any] = request.get_json() #type: ignore
        payment_method_id = data.get('payment_method_id')
        payment_id = data.get('payment_id')
        
        if not payment_method_id:
            return jsonify({'error': 'Missing payment method'}), 400
        
        # Configure Stripe
        stripe.api_key = app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')
        
        # Retrieve payment method to get card country
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        if payment_method.type == 'card' and payment_method.card:
            card_country = payment_method.card.country
        
        # Get payment amount from database
        payment: Payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        base_amount = float(payment.amount_sent_original)
        
        # Calculate fees
        fees = calculate_service_fee(base_amount, card_country, payment.currency_code)
        
        return jsonify({
            'card_country': card_country,
            'fees': fees,
            'base_amount': base_amount,
            'total_amount': base_amount + fees['total_service_fee']
        })
        
    except stripe.error.StripeError as e: #type: ignore
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp_api_user.route('/stripe/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create PaymentIntent with calculated fees"""
    try:
        data: dict[str, Any] = request.get_json() #type: ignore
        payment_id = data.get('payment_id')
        payment_method_id = data.get('payment_method_id')
        if not payment_method_id:
            raise PaymentError("Stripe: Couldn't get payment method ID")
        fees = FeeStructure.from_dict(data.get('fees', {}).get('breakdown', {}))
        
        # Configure Stripe
        stripe.api_key = app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')
        
        # Get payment from database
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        base_amount = float(payment.amount_sent_original)
        total_amount = base_amount + fees.total_service_fee
        
        # Convert to cents (or keep as-is for zero-decimal currencies)
        zero_decimal_currencies = {
            'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA', 'PYG',
            'RWF', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'
        }
        
        is_zero_decimal = payment.currency_code.upper() in zero_decimal_currencies
        amount_in_cents = int(total_amount) if is_zero_decimal else int(total_amount * 100)
        
        # Create PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount_in_cents,
            currency=payment.currency_code.lower(),
            payment_method=payment_method_id,
            confirmation_method='automatic',
            confirm=False,
            metadata={
                'project': 'order_master',
                'payment_id': str(payment_id),
                'base_amount': str(base_amount),
                'service_fee': str(fees.service_fee),
                'send_to_wise': str(fees.send_to_wise),
                'send_to_bank': str(fees.send_to_bank)
            }
        )
        
        return jsonify({
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        })
        
    except stripe.error.StripeError as e: #type: ignore
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
