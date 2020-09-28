'''
Contains api endpoint routes of the application
'''
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.models import User
from app.orders.models import OrderProduct, OrderProductStatusEntry, Suborder

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


# @admin_api.route('/order', defaults={'order_id': None})
# @admin_api.route('/order/<order_id>')
# @roles_required('admin')
# def get_orders(order_id):
#     '''
#     Returns all or selected orders in JSON:
#     '''
#     orders = Order.query.all() \
#         if order_id is None \
#         else Order.query.filter_by(id=order_id)

#     return jsonify(list(map(lambda entry: entry.to_dict(), orders)))

# @admin_api.route('/order/<order_id>', methods=['POST'])
# @roles_required('admin')
# def save_order(order_id):
#     '''
#     Updates existing order
#     Payload is provided in JSON
#     '''
#     order_input = request.get_json()
#     order = Order.query.get(order_id)
#     if not order:
#         abort(Response(f'No order {order_id} was found', status=404))

#     if order_input.get('status') is not None:
#         order.status = order_input['status']

#     if order_input.get('tracking_id') is not None:
#         order.tracking_id = order_input['tracking_id']

#     if order_input.get('tracking_url') is not None:
#         order.tracking_url = order_input['tracking_url']

#     order.when_changed = datetime.now()

#     db.session.commit()
#     return jsonify(order.to_dict())
