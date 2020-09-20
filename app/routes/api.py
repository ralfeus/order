'''
Contains api endpoint routes of the application
'''
from decimal import Decimal
from datetime import datetime
import os.path

from more_itertools import map_reduce

from flask import Blueprint, Response, abort, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db, shipping
from app.models import \
    Country, Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
    Shipping, ShippingRate, Subcustomer, Suborder, Transaction, TransactionStatus, User
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
@login_required
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
        shipping_method_id=request_data['shipping'],
        phone=request_data['phone'],
        comment=request_data['comment'],
        subtotal_krw=0,
        when_created=datetime.now()
    )
    suborders = []
    order_products = []
    errors = []
    # ordertotal_weight = 0
    for suborder_data in request_data['suborders']:
        try:
            suborder = Suborder(
                order=order,
                subcustomer=parse_subcustomer(suborder_data['subcustomer']),
                buyout_date=datetime.strptime(suborder_data['buyout_date'], '%d.%m.%Y') \
                    if suborder_data.get('buyout_date') else None,
                when_created=datetime.now()
            )
        except IndexError as e:
            abort(Response(f"""Couldn't find subcustomer and provided data 
                               doesn't allow to create new one. Please provide
                               new subcustomer data in format: 
                               <ID>, <Name>, <Password>
                               Erroneous data is: {suborder_data['subcustomer']}""",
                           status=400))
        for item in suborder_data['items']:
            product = Product.query.get(item['item_code'])
            if product:
                order_product = OrderProduct(
                    suborder=suborder,
                    product_id=product.id,
                    price=product.price,
                    quantity=int(item['quantity']),
                    status='Pending',
                    when_created=datetime.now())
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
    order.shipping_krw = int(Decimal(shipping.get_shipment_cost(
        order.country, order.total_weight + order.shipping_box_weight)))
    order.shipping_rur = order.shipping_krw * Currency.query.get('RUR').rate
    order.shipping_usd = order.shipping_krw * Currency.query.get('USD').rate
    order.total_krw = order.subtotal_krw + order.shipping_krw
    order.total_rur = order.subtotal_rur + order.shipping_rur
    order.total_usd = order.subtotal_usd + order.shipping_usd
    db.session.add(order)
    try:
        db.session.commit()
        result = {
            'status': 'warning' if len(errors) > 0 else 'success',
            'order_id': order.id,
            'message': errors
        }
    except (IntegrityError, OperationalError) as e:
        result = {
            'status': 'error',
            'message': "Couldn't add order due to input error. Check your form and try again."
        }
    return jsonify(result)

def parse_subcustomer(subcustomer_data):
    parts = subcustomer_data.split(',')
    for part in parts:
        subcustomer = Subcustomer.query.filter(or_(
            Subcustomer.name == part, Subcustomer.username == part)).first()
        if subcustomer:
            return subcustomer
    subcustomer = Subcustomer(
        username=parts[0].strip(), 
        name=parts[1].strip(), 
        password=parts[2].strip(),
        when_created=datetime.now()) 
    db.session.add(subcustomer)
    return subcustomer


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

@api.route('/product', defaults={'product_id': None})
@api.route('/product/<product_id>')
@login_required
def get_product(product_id):
    '''
    Returns list of products in JSON
    '''
    product_query = None
    error_message = None
    if product_id:
        error_message = f"No product with code <{product_id}> was found"
        stripped_id = product_id.lstrip('0')
        product_query = Product.query.filter_by(available=True). \
            filter(Product.id.endswith(stripped_id)).all()
        product_query = [product for product in product_query
                        if product.id.lstrip('0') == stripped_id]
    else:
        error_message = "There are no available products in store now"
        product_query = Product.query.filter_by(available=True).all()
    if len(product_query) != 0:
        return jsonify(Product.get_products(product_query))
    abort(Response(error_message, status=404))

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
