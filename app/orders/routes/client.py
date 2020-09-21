from flask import Response, abort, current_app, escape, request, render_template, \
     send_file, send_from_directory, flash, url_for
from flask_security import current_user, login_required

from app.orders import bp_client_admin, bp_client_user
from app.orders.models import Order

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"orders/static/{file}")

@bp_client_user.route('/new')
@login_required
def new_order():
    '''
    New order form
    '''
    return render_template('new_order.html', load_excel=request.args.get('upload') is not None)

@bp_client_user.route('/<order_id>')
@login_required
def get_order(order_id):
    '''
    Existing order form
    '''
    order = Order.query.filter_by(id=order_id, user=current_user).first()
    if not order:
        abort(Response(escape(f"No order <{order_id}> was found"), status=404))
    return render_template('new_order.html', order_id=order_id)