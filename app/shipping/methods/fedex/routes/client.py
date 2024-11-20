'''Client routes for Fedex shipping'''
import os
from flask import Response, abort, current_app, request, send_file
from flask_security import roles_required

from app.orders.models.order import Order
from ..models.fedex import get_label

from .. import bp_client_admin

@bp_client_admin.route('/')
@roles_required('admin')
def admin_edit():
    pass

@bp_client_admin.route('/label')
@roles_required('admin')
def admin_print_label():
    order = Order.query.get(request.args.get('order_id'))
    if order is None:
        abort(status=404)
    try:
        return send_file(get_label(order.tracking_id))
    except:
        abort(Response(status=404, response="No FedEx label for order {order.id}"))