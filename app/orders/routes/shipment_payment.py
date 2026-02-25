''' Client routes for separate shipment payment flow '''
from flask import Response, abort, current_app, request, render_template
from flask_security import current_user, login_required

from app.orders import bp_client_user

from ..models.order import Order
from ..models.order_status import OrderStatus


@bp_client_user.route('/<order_id>/shipment/pay')
@login_required
def user_shipment_pay(order_id):
    '''Shipment payment checkout page for end users'''
    from app.shipping.methods.separate.models.separate_shipping import SeparateShipping
    order = Order.query.filter_by(id=order_id).filter_by(user=current_user).first() \
        if not current_user.has_role('admin') \
        else Order.query.get(order_id)
    if not order:
        abort(Response(f"No order <{order_id}> was found", status=404))
    if not isinstance(order.shipping, SeparateShipping):
        abort(Response("Order shipping method does not require separate shipping payment", status=409))
    if order.status != OrderStatus.packed:
        abort(Response("Order is not in packed status", status=409))
    return render_template('shipment_payment.html',
        order=order,
        stripe_key=current_app.config.get('PAYMENT', {}).get('stripe', {}).get('api_key'),
        stripe_payment_key=current_app.config.get('PAYMENT', {}).get('stripe', {}).get('api_payment_key'))


@bp_client_user.route('/<order_id>/shipment/pay/success')
@login_required
def user_shipment_pay_success(order_id):
    '''Handles successful shipment payment from Stripe redirect'''
    import stripe

    stripe.api_key = current_app.config.get('PAYMENT', {}).get('stripe', {}).get('api_secret')

    payment_intent_id = request.args.get('payment_intent')
    if not payment_intent_id:
        return render_template('shipment_payment_result.html', success=False,
                               message="Missing payment intent")

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id,
                                               expand=['latest_charge'])
    except Exception as e:
        current_app.logger.exception("Error retrieving Stripe payment intent: %s", e)
        return render_template('shipment_payment_result.html', success=False,
                               message="Could not verify payment")

    if intent.status != 'succeeded':
        return render_template('shipment_payment_result.html', success=False,
                               message=f"Payment status: {intent.status}")

    intent_order_id = intent.metadata.get('order_id', '')
    if intent_order_id != order_id:
        current_app.logger.warning(
            "Shipment payment intent order_id mismatch: %s vs %s", intent_order_id, order_id)
        return render_template('shipment_payment_result.html', success=False,
                               message="Payment/order mismatch")

    order = Order.query.get(order_id)
    if not order:
        return render_template('shipment_payment_result.html', success=False,
                               message="Order not found")

    from app import db
    order.set_status(OrderStatus.shipment_is_paid, current_user)
    db.session.commit() #type: ignore

    # Optionally create consignment at shipping provider
    if order.shipping.is_consignable():
        try:
            from app.models.address import Address
            from app.shipping.models.shipping_contact import ShippingContact
            from app.shipping.routes.api import default_box

            payee = order.get_payee()
            if payee:
                sender = payee.address
                sender_contact = ShippingContact(name=payee.contact_person, phone=payee.phone)
            else:
                sender = None
                sender_contact = ShippingContact(name='', phone='')

            recipient = Address(
                address_1_eng=order.address,
                address_2_eng='',
                city_eng=order.city_eng,
                country_id=order.country_id,
                zip=order.zip
            )
            rcpt_contact = ShippingContact(name=order.customer_name, phone=order.phone)

            raw_items = []
            try:
                raw_items = order.params["shipping.items"].replace("|", "/").splitlines()
            except Exception:
                raw_items = [
                    f"{op.product.name_english}/{op.quantity}/{int(op.price / 3)}"
                    for op in order.order_products
                ]
            items = order.shipping.get_shipping_items(raw_items)

            boxes = list(order.boxes) if order.boxes.count() > 0 else [default_box]
            if not boxes[0].weight:
                boxes[0].weight = order.total_weight + (order.shipping_box_weight or 0)

            result = order.shipping.consign(
                sender, sender_contact, recipient, rcpt_contact, items, boxes,
                config=current_app.config.get("SHIPPING_AUTOMATION")
            )
            order.tracking_id = result.tracking_id
            order.tracking_url = f'https://t.17track.net/en#nums={result.tracking_id}'
            db.session.commit() #type: ignore
        except Exception as e:
            current_app.logger.warning("Shipment consignment failed for %s: %s", order_id, e)

    return render_template('shipment_payment_result.html', success=True,
                           order_id=order_id)
