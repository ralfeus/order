'''
Contains api endpoint routes of the application
'''
from datetime import datetime
from functools import reduce
from more_itertools import map_reduce
import openpyxl
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request, send_file
from flask_security import current_user, login_required, roles_required

from app import db
from app.invoices.models import Invoice
from app.models import \
    Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
    User, Suborder, Transaction, TransactionStatus

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')

@admin_api.route('/order_product')
@login_required
@roles_required('admin')
def get_order_products():
    '''
    Returns list of ordered items. So far implemented only for admins
    '''
    order_products_query = OrderProduct.query
    if request.values.get('order_id'):
        order_products_query = order_products_query.filter(or_(
            OrderProduct.order_id == request.values['order_id'],
            OrderProduct.suborder.has(Suborder.order_id == request.values['order_id'])))

    return jsonify(list(map(lambda order_product: order_product.to_dict(), order_products_query.all())))

@admin_api.route('/order_product/<int:order_product_id>', methods=['POST'])
@roles_required('admin')
def save_order_product(order_product_id):
    '''
    Modifies order products
    Order product payload is received as JSON
    '''
    payload = request.get_json()
    if not payload:
        return Response(status=304)
    order_product = OrderProduct.query.get(order_product_id)
    if not order_product:
        abort(Response(f"Order product ID={order_product_id} wasn't found", status=404))

    editable_attributes = ['product_id', 'price', 'quantity', 'subcustomer', 
                           'private_comment', 'public_comment', 'status']
    for attr in editable_attributes:
        if payload.get(attr):
            setattr(order_product, attr, type(getattr(order_product, attr))(payload[attr]))
            order_product.when_changed = datetime.now()
    try:
        order_product.suborder.order.update_total()
        db.session.commit()
        return jsonify(order_product.to_dict())
    except Exception as e:
        abort(Response(str(e), status=500))

@admin_api.route('/order_product/<int:order_product_id>/status/<order_product_status>', methods=['POST'])
@roles_required('admin')
def admin_set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    order_product = OrderProduct.query.get(order_product_id)
    order_product.status = order_product_status
    db.session.add(OrderProductStatusEntry(
        order_product=order_product,
        status=order_product_status,
        # set_by=current_user,
        user_id=current_user.id,
        set_at=datetime.now()
    ))

    db.session.commit()

    return jsonify({
        'order_product_id': order_product_id,
        'order_product_status': order_product_status,
        'status': 'success'
    })

@admin_api.route('/order_product/<int:order_product_id>/status/history')
@roles_required('admin')
def admin_get_order_product_status_history(order_product_id):
    history = OrderProductStatusEntry.query.filter_by(order_product_id=order_product_id)
    if history.count():
        return jsonify(list(map(lambda entry: {
            'set_by': entry.set_by.username,
            'set_at': entry.set_at.strftime('%Y-%m-%d %H:%M:%S') if entry.set_at else '',
            'status': entry.status
        }, history)))
    else:
        abort(Response(f'No order product ID={order_product_id} found', status=404))

@admin_api.route('/product', defaults={'product_id': None})
@admin_api.route('/product/<product_id>')
@roles_required('admin')
def admin_get_product(product_id):
    '''
    Returns list of products in JSON:
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
    product_query = None
    if product_id:
        product_query = Product.query.filter_by(id=product_id)
    else:
        product_query = Product.query.all()
    return jsonify(Product.get_products(product_query))

@admin_api.route('/product', methods=['POST'])
@roles_required('admin')
def save_product():
    '''
    Saves updates in product or creates new product
    '''
    payload = request.get_json()
    if not payload.get('id'):
        abort(Response('No product ID is provided', status=400))

    product = Product.query.get(payload['id'])
    if not product:
        product = Product()
        product.id = payload['id']
        db.session.add(product)

    editable_attributes = ['name', 'name_english', 'name_russian', 'price',
                           'points', 'weight', 'available']
    for attr in editable_attributes:
        if payload.get(attr):
            setattr(product, attr, payload[attr])
            product.when_changed = datetime.now()

    db.session.commit()

    return jsonify({
        'status': 'success'
    })

@admin_api.route('/product/<product_id>', methods=['DELETE'])
@roles_required('admin')
def delete_product(product_id):
    '''
    Deletes a product by its product code
    '''
    result = None
    try:
        Product.query.filter_by(id=product_id).delete()
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete product {product_id} as it's used in some orders"
        })
        result.status_code = 409

    return result

@admin_api.route('/transaction', defaults={'transaction_id': None})
@admin_api.route('/transaction/<int:transaction_id>')
@roles_required('admin')
def admin_get_transactions(transaction_id):
    '''
    Returns all or selected transactions in JSON:
    {
        id: transaction ID,
        user_id: ID of the transaction owner,
        currency: transaction original currency,
        amount_original: amount in original currency,
        amount_krw: amount in KRW at the time of transaction,
        status: transaction status ('pending', 'approved', 'rejected', 'cancelled')
    }
    '''
    transactions = Transaction.query.all() \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), transactions)))

@admin_api.route('/transaction/<int:transaction_id>', methods=['POST'])
@roles_required('admin')
def admin_save_transaction(transaction_id):
    '''
    Saves updates in user profile.
    '''
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(404)
    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(f"Can't update transaction in state <{transaction.status}>", status=409))
    if payload:
        if payload.get('amount_original'):
            transaction.amount_sent_original = payload['amount_original']
        if payload.get('currency_code'):
            transaction.currency = Currency.query.get(payload['currency_code'])
        if payload.get('amount_krw'):
            transaction.amount_sent_krw = payload['amount_krw']
        if payload.get('amount_received_krw'):
            transaction.amount_received_krw = payload['amount_received_krw']
        if payload.get('status') and transaction.status != TransactionStatus.approved:
            transaction.status = payload['status'].lower()
    else:
        abort(400)
    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    db.session.commit()

    return jsonify(transaction.to_dict())

@admin_api.route('/user/<user_id>', methods=['DELETE'])
@roles_required('admin')
def delete_user(user_id):
    '''
    Deletes a user by its user_id
    '''
    result = None
    try:
        User.query.filter_by(id=user_id).delete(synchronize_session='fetch')
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
        
@admin_api.route('/user/<int:user_id>', methods=['POST'])
@roles_required('admin')
def save_user(user_id):    
    user_input = request.get_json()
    if not user_input:
        abort(Response(f"Can't update user <{user_id}> - no data provided",
                       status=400))
    user = User.query.get(user_id)
    if not user:
        user = User()

    if user_input.get('username') is not None:
        user.username = user_input['username']
    
    if user_input.get('email') is not None:
        user.email = user_input['email']

    if user_input.get('password') is not None:
        user.password = user_input['password']

    if user_input.get('enabled') is not None:
        user.enabled = user_input['enabled']

    if not user.id:
        db.session.add(user)

    user.when_changed = datetime.now()

    db.session.commit()
    return jsonify(user.to_dict())


@admin_api.route('/order', defaults={'order_id': None})
@admin_api.route('/order/<order_id>')
@roles_required('admin')
def get_orders(order_id):
    '''
    Returns all or selected orders in JSON:
    '''
    orders = Order.query.all() \
        if order_id is None \
        else Order.query.filter_by(id=order_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), orders)))

@admin_api.route('/order/<order_id>', methods=['POST'])
@roles_required('admin')
def save_order(order_id):
    '''
    Updates existing order
    Payload is provided in JSON
    '''
    order_input = request.get_json()
    order = Order.query.get(order_id)
    if not order:
        abort(Response(f'No order {order_id} was found', status=404))

    if order_input.get('status') is not None:
        order.status = order_input['status']

    if order_input.get('tracking_id') is not None:
        order.tracking_id = order_input['tracking_id']

    if order_input.get('tracking_url') is not None:
        order.tracking_url = order_input['tracking_url']

    order.when_changed = datetime.now()

    db.session.commit()
    return jsonify(order.to_dict())
