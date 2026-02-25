''' API routes for separate shipment payment flow '''
from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required

from app.orders import bp_api_user

from ..models.order import Order
from ..models.order_status import OrderStatus


@bp_api_user.route('/<order_id>/shipment/pay', methods=['POST'])
@login_required
def user_create_shipment_payment_intent(order_id):
    '''Creates a Stripe payment intent for the shipment cost of a packed order.

    Only applicable to orders with SeparateShipping method and "packed" status.
    Fees are calculated using the same fee structure as regular Stripe payments.
    '''
    from app.shipping.methods.separate.models.separate_shipping import SeparateShipping
    from app.payments.routes.payment_methods.stripe import calculate_service_fee
    import stripe

    order: Order = Order.query.filter_by(id=order_id).filter_by(user=current_user).first() \
        if not current_user.has_role('admin') \
        else Order.query.get(order_id)
    if order is None:
        abort(Response(f"No order <{order_id}> was found", status=404))
    if not isinstance(order.shipping, SeparateShipping):
        abort(Response("Order shipping method is not SeparateShipping", status=409))
    if order.status != OrderStatus.packed:
        abort(Response("Order is not in packed status", status=409))

    data = request.get_json() or {}
    payment_method_id = data.get('payment_method_id')
    if not payment_method_id:
        abort(Response("Missing payment_method_id", status=400))

    # Use EUR amount (shipping_cur2); fall back to computing from KRW
    from app.currencies.models.currency import Currency
    shipping_eur = float(order.shipping_cur2) if order.shipping_cur2 else \
        order.shipping_krw * float(Currency.query.get('EUR').rate)

    stripe.api_key = current_app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')
    payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
    card_country = ''
    if payment_method.type == 'card' and payment_method.card:
        card_country = payment_method.card.country

    fees = calculate_service_fee(shipping_eur, card_country, 'EUR')
    total = fees.send_to_stripe

    intent = stripe.PaymentIntent.create(
        amount=int(total * 100),  # EUR in cents
        currency='eur',
        payment_method=payment_method_id,
        confirmation_method='automatic',
        confirm=False,
        metadata={
            'project': 'order_master',
            'order_id': order_id,
            'service_fee': str(fees.service_fee),
            'to_shipping_provider': str(round(shipping_eur, 2)),
        }
    )
    return jsonify({
        'client_secret': intent.client_secret,
        'payment_intent_id': intent.id,
        'shipping_amount': round(shipping_eur, 2),
        'service_fee': round(total - shipping_eur, 2),
        'total': total,
        'currency': 'EUR',
    })
