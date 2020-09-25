from flask import Response, abort, escape, request, render_template, send_file
from flask_security import current_user, login_required, roles_required

from app.orders import bp_client_admin, bp_client_user
from app.currencies.models import Currency
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

@bp_client_user.route('/')
@login_required
def get_orders():
    '''
    Orders list for users
    '''
    return render_template('orders.html')

@bp_client_admin.route('/')
@roles_required('admin')
def admin_get_orders():
    '''
    Order management
    '''
    usd_rate = Currency.query.get('USD').rate
    return render_template('admin_orders.html', usd_rate=usd_rate)

@bp_client_admin.route('/<order_id>')
@roles_required('admin')
def admin_get_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        abort(Response("The order <{order_id}> was not found", status=404))
    if request.values.get('view') == 'print':
        return render_template('order_print_view.html', order=order)
    abort(501)
