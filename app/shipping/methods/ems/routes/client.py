'''Client routes for EMS shipping'''
import json
from flask import Response, abort, current_app, render_template, request
from flask_security import roles_required

from app import db
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from ..models.ems import EMS

from .. import bp_client_admin

@bp_client_admin.route('/label')
@roles_required('admin')
def admin_print_label() -> str:
    order_id = request.args.get('order_id')
    order:Order = Order.query.get(order_id)
    if order is None:
        abort(status=404)
    shipping: EMS = order.shipping
    if not isinstance(shipping, EMS):
        abort(Response(f"The order {order_id} is not shipped by EMS", status=400))
    export_id = ''
    if order.invoice is not None and order.invoice.export_id is not None:
        export_id = order.invoice.export_id
    try:
        consignment = shipping.print(order, current_app.config.get("SHIPPING_AUTOMATION"))
        order.status = OrderStatus.shipped
        db.session.commit()
        return render_template('label.html', consignment=consignment, export_id=export_id)
    except Exception as e:
        return Response(str(e), status=400)
