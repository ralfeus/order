'''
Contains api endpoint routes of the application
'''
from datetime import datetime
import os.path

from more_itertools import map_reduce

from flask import Blueprint, Response, abort, current_app, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import Country, Shipping, ShippingRate, User
from app.orders.models import Order, OrderProduct, OrderProductStatusEntry, \
                              Suborder
from app.currencies.models import Currency
from app.transactions.models import Transaction, TransactionStatus
from app.tools import rm, write_to_file

api = Blueprint('api', __name__, url_prefix='/api/v1')

@api.route('/country')
@login_required
def get_countries():
    countries = Country.query.join(ShippingRate)
    return jsonify(list(map(lambda c: c.to_dict(), countries)))

@api.route('/currency')
def get_currency_rate():
    '''
    Returns currency rates related to KRW in JSON:
        {
            currency code: currency rate to KRW
        }
    '''
    currencies = {c.code: str(c.rate) for c in Currency.query.all()}
    return jsonify(currencies)

@api.route('/order_product')
@login_required
def get_order_products():
    '''
    Returns list of ordered items.
    '''
    order_products = OrderProduct.query
    if request.args.get('context') and current_user.username == 'admin':
        order_products = order_products.all()
    else:
        order_products = order_products.filter(
            OrderProduct.suborder.has(Suborder.order.has(Order.user == current_user)))
    return jsonify(list(map(lambda order_product: order_product.to_dict(),
                            order_products)))

@api.route('/order_product/<int:order_product_id>/status/<order_product_status>', methods=['POST'])
def set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    order_product = OrderProduct.query.get(order_product_id)
    order_product.status = order_product_status
    db.session.add(OrderProductStatusEntry(
        order_product=order_product,
        status=order_product_status,
        # set_by=current_user,
        user_id=1,
        set_at=datetime.now()
    ))

    db.session.commit()

    return jsonify({
        'order_product_id': order_product_id,
        'order_product_status': order_product_status,
        'status': 'success'
    })

@api.route('/order_product/<int:order_product_id>/status/history')
def get_order_product_status_history(order_product_id):
    history = OrderProductStatusEntry.query.filter_by(order_product_id=order_product_id)
    if history.count():
        return jsonify(list(map(lambda entry: {
            'set_by': entry.set_by.username,
            'set_at': entry.set_at.strftime('%Y-%m-%d %H:%M:%S'),
            'status': entry.status
        }, history)))
    else:
        result = jsonify({
            'status': 'error',
            'message': f'No order product ID={order_product_id} found'
        })
        result.status_code = 404
        return result

@api.route('/shipping', defaults={'country_id': None, 'weight': None})
@api.route('/shipping/<country_id>', defaults={'weight': None})
@api.route('/shipping/<country_id>/<int:weight>')
@login_required
def get_shipping_methods(country_id, weight):
    '''
    Returns shipping methods available for specific country and weight (if both provided)
    '''
    country_name = ''
    shipping_methods = Shipping.query.join(ShippingRate)
    if country_id:
        country = Country.query.get(country_id)
        if country:
            country_name = country.name
            shipping_methods = shipping_methods.filter(ShippingRate.destination == country_id)
    if weight:
        shipping_methods = shipping_methods.filter(ShippingRate.weight >= weight)
    if shipping_methods.count():
        return jsonify(list(map(lambda s: s.to_dict(), shipping_methods)))
    abort(Response(
        f"Couldn't find shipping method to send {weight}g parcel to {country_name}",
        status=409))

@api.route('/shipping/rate/<country>/<shipping_method_id>/<weight>')
@api.route('/shipping/rate/<country>/<weight>', defaults={'shipping_method_id': None})
def get_shipping_rate(country, shipping_method_id, weight):
    '''
    Returns shipping cost for provided country and weight
    Accepts parameters:
        country - Destination country
        shipping_method_id - ID of the shipping method
        weight - package weight in grams
    Returns JSON
    '''
    # print(country, weight)
    shipping_rate_query = ShippingRate.query. \
        filter_by(destination=country). \
        filter(ShippingRate.weight > weight)
    if shipping_rate_query.count():
        if shipping_method_id:
            rate = shipping_rate_query. \
                filter_by(shipping_method_id=shipping_method_id, ). \
                order_by(ShippingRate.weight). \
                first()
            return jsonify({
                'shipping_cost': rate.rate
            })
        else:
            rates = map_reduce(shipping_rate_query,
                keyfunc=lambda i: i.shipping_method_id,
                valuefunc=lambda i: i.rate,
                reducefunc=min 
            )
            return jsonify(rates)
    else:
        abort(Response(
            f"Couldn't find rate for {weight}g parcel to {country.title()}",
            status=409
        ))

@api.route('/transaction', defaults={'transaction_id': None})
@api.route('/transaction/<int:transaction_id>')
@login_required
def get_transactions(transaction_id):
    '''
    Returns user's or all transactions in JSON:
    {
        id: transaction ID,
        user_id: ID of the transaction owner,
        user_name: name of the transaction owner,
        currency: transaction original currency,
        amount_original: amount in original currency,
        amount_krw: amount in KRW at the time of transaction,
        status: transaction status ('pending', 'approved', 'rejected', 'cancelled')
    }
    '''
    transactions = Transaction.query \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)
    transactions = transactions.filter_by(user=current_user)
    return jsonify(list(map(lambda tran: tran.to_dict(), transactions)))
    
@api.route('/transaction/<int:transaction_id>', methods=['POST'])
@login_required
def save_transaction(transaction_id):
    '''
    Saves updates in transaction
    '''
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(404)

    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(
            f"Can't update transaction in state <{transaction.status}>", status=409))
    if payload['status'] == 'cancelled':
        transaction.status = TransactionStatus.cancelled

    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    db.session.commit()

    return jsonify({
        'id': transaction.id,
        'user_id': transaction.user_id,
        'amount_original': transaction.amount_original,
        'amount_original_string': transaction.currency.format(transaction.amount_original),
        'amount_krw': transaction.amount_krw,
        'currency_code': transaction.currency.code,
        'evidence_image': transaction.proof_image,
        'status': transaction.status.name,
        'when_created': transaction.when_created.strftime('%Y-%m-%d %H:%M:%S'),
        'when_changed': transaction.when_changed.strftime('%Y-%m-%d %H:%M:%S') if transaction.when_changed else ''
    })

@api.route('/v1/transaction/<int:transaction_id>/evidence', methods=['POST'])
@login_required
def upload_transaction_evidence(transaction_id):
    transaction = Transaction.query.get(transaction_id)
    if current_user.username != 'admin' and \
        current_user != transaction.user:
        abort(403)
    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(
            f"Can't update transaction in state <{transaction.status}>", status=409))
    if request.files and request.files['file'] and request.files['file'].filename:
        file = request.files['file']
        rm(transaction.proof_image)
        image_data = file.read()
        file_name = os.path.join(
            current_app.config['UPLOAD_PATH'],
            str(current_user.id),
            datetime.now().strftime('%Y-%m-%d.%H%M%S.%f')) + \
            ''.join(os.path.splitext(file.filename)[1:])
        write_to_file(file_name, image_data)
    
        transaction.proof_image = file_name
        transaction.when_changed = datetime.now()
        transaction.changed_by = current_user
        db.session.commit()
    else:
        abort(Response("No file is uploaded", status=400))
    return jsonify({})

@api.route('/user')
@login_required
def get_user():
    '''
    Returns list of products in JSON:
        {
            'id': product ID,
            'username': user name,
            'email': user's email,
            'creted': user's profile created,
            'changed': last profile change
        }
    '''
    user_query = User.query.all()
    return jsonify(User.get_user(user_query))
