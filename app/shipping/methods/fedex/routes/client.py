'''Client routes for Fedex shipping'''
import os
from flask import Response, abort, current_app, render_template, request, send_file
from flask_security import roles_required

from app.orders.models.order import Order
from app.shipping.models.shipping import Shipping
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
    tracking_id = request.args.get('tracking_id')
    if order is None and tracking_id is None:
        abort(status=404)
    try:
        return send_file(get_label(tracking_id or order.tracking_id)) # type: ignore
    except:
        if order is not None:
            response = f"No FedEx label for order {order.id}"
        else:
            response = f"No FedEx label for tracking {tracking_id}"
        abort(Response(status=404, response=response))

@bp_client_admin.route('/<shipping_id>')
@roles_required('admin')
def admin_edit_settings(shipping_id: int):
    fedex = Shipping.query.get(shipping_id)
    if fedex is None:
        return f"The shipping method <{shipping_id}> wasn't found", 404
    return render_template('settings.html', shipping_id=fedex.id, settings=fedex.settings)