'''
Contains all routes of the application
'''
from datetime import datetime

from flask import Response, jsonify, request, send_from_directory
from flask_login import current_user, login_required, login_user

from app import app, db
from app.models import Currency, Order, OrderProduct, Product, ShippingRate, User

@app.route('/')
def index():
    '''
    Entry point to the application.
    Takes no arguments
    '''
    return send_from_directory('static/html', 'index.html')

@app.route('/admin/<key>')
def admin(key):
    if key == app.config['ADMIN_HASH']:
        login_user(User(0), remember=True)
    if current_user.is_anonymous:
        return Response('Anonymous access is denied', mimetype='text/html')
    else:
        return send_from_directory('static/html', 'admin.html')

@app.route('/api/currency')
def get_currency_rate():
    '''
    Returns currency rates related to KRW in JSON:
        {
            currency code: currency rate to KRW
        }
    '''
    currencies = {c.code: c.rate for c in Currency.query.all()}
    return jsonify(currencies)


@app.route('/api/order', methods=['POST'])
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
    order = Order(
        name=request_data['name'],
        address=request_data['address'],
        country=request_data['country'],
        phone=request_data['phone'],
        comment=request_data['comment'],
        time_created=datetime.now()
    )
    order_products = [OrderProduct(
        order=order,
        subcustomer=product['subcustomer'],
        product_id=item['item_code'],
        quantity=item['quantity'],
        status='Pending'
    ) for product in request_data['products'] for item in product['items']]
    order.order_products = order_products
    db.session.add(order)
    db.session.commit()
    return jsonify({
        'status': 'success',
        'order_id': order.id
    })

@app.route('/api/order_product')
@login_required
def get_orders():
    '''
    Returns list of ordered items. So far implemented only for admins
    '''
    order_products = OrderProduct.query.all()
    return jsonify(list(map(lambda order_product: {
        'order_id': order_product.order_id,
        'order_product_id': order_product.id,
        'customer': order_product.order.name,
        'subcustomer': order_product.subcustomer,
        'product_id': order_product.product_id,
        'product': order_product.product.name_english,
        'comment': order_product.order.comment,
        'quantity': order_product.quantity,
        'status': order_product.status
        }, order_products)))

################# TO BE DONE #####################
@app.route('/api/order_product/status/<int:order_product_id>/<order_product_status>', methods=['POST'])
def set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    order_product = OrderProduct.query.get(order_product_id)
    order_product.status = order_product_status

    # db.session.merge(order_product) 
    db.session.commit()

    return jsonify({
        'order_product_id': order_product_id,
        'order_product_status': order_product_status,
        'status': 'success'
    })

@app.route('/api/product')
def get_product():
    '''
    Returns list of products where product ID starts with provided value
    Accepts payload:
        term : part of product ID
    Returns list of products in JSON:
        {
            'value': product ID,
            'label': product english and russian name,
            'price': product price in KRW,
            'weight': product weight,
            'points': product points
        }
    '''
    products = Product.query.filter(Product.id.like(request.values['term'] + '%'))
    return jsonify(list(map(lambda product: {
        'value': product.id,
        'label': product.name_english + " | " + product.name_russian,
        'price': product.price,
        'weight': product.weight,
        'points': product.points
        }, products)))

@app.route('/api/shipping_cost/<country>/<weight>')
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
        response.status_code = 400
        return response
    else:
        # print(rate)
        return jsonify({
            'shipping_cost': rate.rate
        })
