'''
Contains api endpoint routes of the application
'''
from decimal import Decimal
from datetime import datetime
import os.path

from flask import Blueprint, Response, abort, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db, shipping
from app.models import \
    Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
    ShippingRate, Transaction, TransactionStatus, User
from app.tools import rm, write_to_file

api = Blueprint('api', __name__, url_prefix='/api/v1')

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

@api.route('/order', defaults={'order_id': None})
@api.route('/order/<order_id>')
@login_required
def get_orders(order_id):
    '''
    Returns all or selected orders in JSON
    '''
    orders = Order.query.filter_by(user=current_user) \
        if order_id is None \
        else Order.query.filter_by(id=order_id, user=current_user)
    if orders.count() == 0:
        abort(Response("No orders were found", status=404))
    elif orders.count() == 1:
        return jsonify(orders.first().to_dict())
    else:
        return jsonify(list(map(lambda entry: entry.to_dict(), orders)))

@api.route('/order', methods=['POST'])
def create_order():
    '''
    Creates order.
    Accepts order details in payload
    Returns JSON:
        {   
            'status': operation status
            'order_id': ID of the created order
        }
    '''
    request_data = request.get_json()
    if not request_data:
        abort(Response("No data is provided", status=400))
    result = {}
    order = Order(
        user=current_user,
        name=request_data['name'],
        address=request_data['address'],
        country=request_data['country'],
        phone=request_data['phone'],
        comment=request_data['comment'],
        when_created=datetime.now()
    )
    order_products = []
    errors = []
    # ordertotal_weight = 0
    for suborder in request_data['products']:
        for item in suborder['items']:
            product = Product.query.get(item['item_code'])
            if product:
                order_product = OrderProduct(
                    order=order,
                    subcustomer=suborder['subcustomer'],
                    product_id=product.id,
                    price=product.price,
                    quantity=int(item['quantity']),
                    status='Pending')
                db.session.add(order_product)
                order_products.append(order_product)
                order.total_weight += product.weight * order_product.quantity
                order.subtotal_krw += product.price * order_product.quantity
            else:
                errors.append(f'{item["item_code"]}: no such product')

    order.order_products = order_products
    order.subtotal_rur = order.subtotal_krw * Currency.query.get('RUR').rate
    order.subtotal_usd = order.subtotal_krw * Currency.query.get('USD').rate
    order.shipping_box_weight = shipping.get_box_weight(order.total_weight)
    order.shipping_krw = Decimal(shipping.get_shipment_cost(
        order.country, order.total_weight + order.shipping_box_weight))
    order.shipping_rur = order.shipping_krw * Currency.query.get('RUR').rate
    order.shipping_usd = order.shipping_krw * Currency.query.get('USD').rate
    order.total_krw = order.subtotal_krw + order.shipping_krw
    order.total_rur = order.subtotal_rur + order.shipping_rur
    order.total_usd = order.subtotal_usd + order.shipping_usd
    db.session.add(order)
    try:
        db.session.commit()
        result = {
            'status': 'warning' if len(errors) else 'success',
            'order_id': order.id,
            'message': errors
        }
    except (IntegrityError, OperationalError) as e:
        result = {
            'status': 'error',
            'message': "Couldn't add order due to input error. Check your form and try again."
        }
    return jsonify(result)

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
            OrderProduct.order.has(Order.user == current_user))
    return jsonify(list(map(lambda order_product: {
        'order_id': order_product.order_id,
        'order_product_id': order_product.id,
        'customer': order_product.order.name,
        'subcustomer': order_product.subcustomer,
        'product_id': order_product.product_id,
        'product': order_product.product.name_english,
        'private_comment': order_product.private_comment,
        'public_comment': order_product.public_comment,
        'comment': order_product.order.comment,
        'quantity': order_product.quantity,
        'status': order_product.status
        }, order_products)))

@api.route('/order_product/<int:order_product_id>', methods=['POST'])
@login_required
def save_order_product(order_product_id):
    '''
    Modifies order products
    '''
    result = None
    order_product_input = request.get_json()
    order_product = OrderProduct.query.get(order_product_id)
    if order_product:
        if (order_product_input and 
            order_product_input.get('context') == 'admin' and
            current_user.username == 'admin'):
            order_product.private_comment = order_product_input['private_comment']
        order_product.public_comment = order_product_input['public_comment']
        order_product.changed_at = datetime.now()
        try:
            db.session.commit()
            result = jsonify({
                'order_id': order_product.order_id,
                'order_product_id': order_product.id,
                'customer': order_product.order.name,
                'subcustomer': order_product.subcustomer,
                'product_id': order_product.product_id,
                'product': order_product.product.name_english,
                'private_comment': order_product.private_comment,
                'public_comment': order_product.public_comment,
                'quantity': order_product.quantity,
                'status': order_product.status
            })
        except Exception as e:
            result = jsonify({
                'status': 'error',
                'message': e
            })
            result.status_code = 500
    else:
        result = jsonify({
            'status': 'error',
            'message': f"Order product ID={order_product_id} wasn't found"
        })
        result.status_code = 404
    return result


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
    if history:
        return jsonify(list(map(lambda entry: {
            'set_by': entry.set_by.username,
            'set_at': entry.set_at,
            'status': entry.status
        }, history)))
    else:
        result = jsonify({
            'status': 'error',
            'message': f'No order product ID={order_product_id} found'
        })
        result.status_code = 404
        return result

@api.route('/product', defaults={'product_id': None})
@api.route('/product/<product_id>')
@login_required
def get_product(product_id):
    '''
    Returns list of products in JSON
    '''
    product_query = None
    if product_id:
        product_query = Product.query.filter_by(id=product_id, available=True).all()
    else:
        product_query = Product.query.filter_by(available=True).all()
    if len(product_query):
        return jsonify(Product.get_products(product_query))
    abort(Response("No products were found", status=404))

@api.route('/product/search/<term>')
def get_product_by_term(term):
    '''
    Returns list of products where product ID or name starts with provided value in JSON:
        {
            'id': product ID,
            'name': product original name,
            'name_english': product english name,
            'name_russian': product russian name,
            'price': product price in KRW,
            'weight': product weight,
            'points': product points
        }
    '''
    product_query = Product.query.filter_by(available=True).filter(or_(
        Product.id.like(term + '%'),
        Product.name.like(term + '%'),
        Product.name_english.like(term + '%'),
        Product.name_russian.like(term + '%')))
    return jsonify(Product.get_products(product_query))

@api.route('/shipping_cost/<country>/<weight>')
def get_shipping_cost(country, weight):
    '''
    Returns shipping cost for provided country and weight
    Accepts parameters:
        country - Destination country
        weight - package weight in grams
    Returns JSON:
        {
            'message': optional message in case of error
            'shipping_cost': shipping cost in KRW
        }
    '''
    # print(country, weight)
    rate = ShippingRate.query. \
        filter(ShippingRate.destination == country, ShippingRate.weight > weight). \
        order_by(ShippingRate.weight). \
        first()
    if rate is None:
        response = jsonify({
            'message': f"Couldn't find rate for {weight}g parcel to {country}"
        })
        response.status_code = 409
        return response
    else:
        # print(rate)
        return jsonify({
            'shipping_cost': rate.rate
        })

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

@api.route('/user/<user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    '''
    Deletes a user by its user_id
    '''
    result = None
    try:
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete user {user_id} as it's used in some orders"
        })
        result.status_code = 409

    return result
    
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
            app.config['UPLOAD_PATH'],
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
        
