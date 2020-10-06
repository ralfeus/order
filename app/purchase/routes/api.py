from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import current_user, login_required, roles_required

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db
from app.purchase import bp_api_admin
from app.orders.models import Order, OrderProduct, Suborder, Subcustomer
from app.products.models import Product
from app.atomy import atomy_login
from app.tools import prepare_datatables_query

@bp_api_admin.route('/order', defaults={'order_id': None})
@roles_required('admin')
def get_purchase_orders():
    '''
    Returns all or selected purchase orders in JSON
    '''
    orders = Order.query
    if not current_user.has_role('admin'):
        orders = orders.filter_by(user=current_user)
    if order_id is not None:
        orders = orders.filter_by(id=order_id)
        if orders.count() == 1:
            return jsonify(orders.first().to_dict())
    if request.args.get('status'):
        orders = orders.filter_by(status=OrderStatus[request.args['status']].name)
    if request.args.get('draw') is not None: # Args were provided by DataTables
        orders, records_total, records_filtered = prepare_datatables_query(
            orders, request.values,
            or_(
                Order.id.like(f"%{request.values['search[value]']}%"),
                Order.user.has(User.username.like(f"%{request.values['search[value]']}%")),
                Order.name.like(f"%{request.values['search[value]']}%")
            )
        )
        return jsonify({
            'draw': request.values['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': list(map(lambda entry: entry.to_dict(), orders))
        })
    if orders.count() == 0:
        abort(Response("No orders were found", status=404))
    else:
        return jsonify(list(map(lambda entry: entry.to_dict(), orders)))

@bp_api_admin.route('', methods=['POST'])
@roles_required('admin')
def create_purhase_order():
    '''
    Creates purchase order.
    Accepts order details in payload
    Returns JSON
    '''
    pass
