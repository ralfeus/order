from datetime import datetime
from decimal import Decimal

from flask import Response, abort, jsonify, request
from flask_security import current_user, login_required, roles_required

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db, shipping
from app.models import Country, Currency, Product
from app.orders import bp_api_admin, bp_api_user
from app.orders.models import Order, OrderProduct, Suborder, Subcustomer

@bp_api_user.route('/', defaults={'order_id': None})
@bp_api_user.route('/<order_id>')
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

@bp_api_user.route('/', methods=['POST'], strict_slashes=False)
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
        country_id=request_data['country'],
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

    # order.order_products = order_products
    order.subtotal_rur = order.subtotal_krw * Currency.query.get('RUR').rate
    order.subtotal_usd = order.subtotal_krw * Currency.query.get('USD').rate
    order.shipping_box_weight = shipping.get_box_weight(order.total_weight)
    order.shipping_krw = int(Decimal(shipping.get_shipment_cost(
        order.country.id, order.total_weight + order.shipping_box_weight)))
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

@bp_api_user.route('/<order_id>', methods=['POST'])
@login_required
def save_order(order_id):
    '''
    Updates existing order
    '''
    order = Order.query.get(order_id) if 'admin' in current_user.roles \
        else Order.query.filter_by(id=order_id, user=current_user).first()
    if not order:
        abort(Response(f"No order <{order_id}> was found", status=404))
    payload = request.get_json()
    if not payload:
        abort(Response("No order data was provided", status=400))
    
    errors = []
    if payload.get('name') and order.name != payload['name']:
        order.name = payload['name']
    if payload.get('address') and order.address != payload['address']:
        order.customer = payload['address']
    if payload.get('country') and order.country_id != payload['country']:
        order.country_id = payload['country']
    if payload.get('shipping') and order.shipping_method_id != payload['shipping']:
        order.shipping_method_id = payload['shipping']
    if payload.get('phone') and order.phone != payload['phone']:
        order.phone = payload['phone']
    if payload.get('comment') and order.comment != payload['comment']:
        order.comment = payload['comment']

    # Edit or add order products
    order_products = list(order.order_products)
    if payload.get('suborders'):
        for suborder in payload['suborders']:
            for item in suborder['items']:
                order_product = [op for op in order_products if
                                    op.subcustomer == suborder['subcustomer'] and
                                    op.product_id == item['item_code']]
                if len(order_product):
                    update_order_product(order, order_product[0], item)
                    order_products.remove(order_product[0])
                else:
                    try:
                        add_order_product(order, suborder, item, errors)
                    except:
                        pass
    
    # Remove order products
    for order_product in order_products:
        delete_order_product(order, order_product)

    order.update_total()

    result = None
    try:
        db.session.commit()
        result = {
            'status': 'warning' if len(errors) > 0 else 'updated',
            'order_id': order.id,
            'message': errors
        }
    except (IntegrityError, OperationalError) as e:
        result = {
            'status': 'error',
            'message': "Couldn't modify order due to input error. Check your form and try again."
        }
    return jsonify(result)

def add_order_product(order, suborder, item, errors):
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
        order.total_weight += product.weight * order_product.quantity
        order.subtotal_krw += product.price * order_product.quantity
        return order_product
    else:
        errors.append(f'{item["item_code"]}: no such product')
        raise Exception(f'{item["item_code"]}: no such product')

def update_order_product(order, order_product, item):
    if order_product.quantity != int(item['quantity']):
        order.total_weight -= order_product.product.weight * order_product.quantity
        order.subtotal_krw -= order_product.price * order_product.quantity
        order_product.quantity = int(item['quantity'])
        order_product.when_changed = datetime.now()
        order.total_weight += order_product.product.weight * order_product.quantity
        order.subtotal_krw += order_product.price * order_product.quantity
        order.when_changed = datetime.now()

def delete_order_product(order, order_product):
    db.session.delete(order_product)
    order.total_weight -= order_product.product.weight * order_product.quantity
    order.subtotal_krw -= order_product.price * order_product.quantity
    order.when_changed = datetime.now()
