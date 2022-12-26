''' Client routes for order related activities '''
import itertools
import json
from flask import Response, abort, current_app, escape, request, render_template, send_file
from flask.globals import current_app
from flask_security import current_user, login_required, roles_required

from app.orders import bp_client_admin, bp_client_user
from app.currencies.models import Currency
from app.orders.models import Order, OrderStatus
from app.settings.models import Setting
from app.tools import stream_and_close
from exceptions import OrderError

file_types = {
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"orders/static/{file}")

@bp_client_admin.route('/dynamic/<path:file>')
@bp_client_user.route('/dynamic/<path:file>')
def get_dynamic(file):
    return render_template(file)

@bp_client_admin.route('/dynamic/admin_order_products.js')
def get_admin_order_products_js():
    from app.orders.signals import admin_order_products_rendering
    extensions = admin_order_products_rendering.send()
    extension_fields = list(itertools.chain(*[
        extension[1]['fields'] for extension in extensions]))
    extension_columns = list(itertools.chain(*[
        extension[1]['columns'] for extension in extensions]))
    return render_template('admin_order_products.js', extension={
        'fields': extension_fields,
        'columns': extension_columns
    })

@bp_client_admin.route('/products')
@roles_required('admin')
def admin_order_products():
    from app.orders.signals import admin_order_products_rendering
    extensions = admin_order_products_rendering.send()
    extension_columns = list(itertools.chain(*[
        extension[1]['columns'] for extension in extensions]))
    return render_template('admin_order_products.html', ext_columns=extension_columns)

@bp_client_user.route('/products')
@login_required
def user_order_products():
    return render_template('order_products.html')

@bp_client_user.route('/new')
@login_required
def user_new_order():
    '''New order form'''
    from ..signals import user_create_sale_order_rendering
    extensions = user_create_sale_order_rendering.send()
    return render_template('new_order.html',
        load_excel=request.args.get('upload') is not None,
        can_create_po=current_user.has_role('allow_create_po'),
        check_subcustomers=Setting.get('order.new.check_subcustomers'),
        free_local_shipping_threshold=current_app.config['FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD'],
        local_shipping_cost=current_app.config['LOCAL_SHIPPING_COST'],
        extensions="\n".join([e[1] for e in extensions]),
        order_id=request.args.get('from_order'),
        make_copy=request.args.get('from_order') is not None)

@bp_client_user.route('/<order_id>')
@login_required
def user_get_order(order_id):
    ''' Existing order view '''
    logger = current_app.logger.getChild('user_get_order')
    order = Order.query
    profile = json.loads(current_user.profile)
    if not current_user.has_role('admin'):
        order = order.filter_by(user=current_user)
    order = order.filter_by(id=order_id).first()
    if not order:
        abort(Response(escape(f"No order <{order_id}> was found"), status=404))
    if order.status == OrderStatus.draft:
        return render_template('new_order.html',
            order_id=order.id,        
            free_local_shipping_threshold=current_app.config['FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD'],
            local_shipping_cost=current_app.config['LOCAL_SHIPPING_COST']
        )
    currency = Currency.query.get(profile.get('currency'))
    if 'currency' in request.values:
        currency = Currency.query.get(request.values['currency'])
        if currency is not None:
            profile['currency'] = currency.code
            current_user.profile = json.dumps(profile)
            from app import db
            db.session.commit()
    if currency is None:
        currency = Currency.query.get('KRW')
    currencies = [{'code': c.code, 'default': c.code == profile.get('currency')}
                  for c in Currency.query if c.enabled]
    rate = currency.get_rate(order.when_created)
    logger.debug("order: %s\ncurrency: %s\nrate: %s", order, currency, rate)
    return render_template('order_view.html', order=order,
        currency=currency, currencies=currencies, rate=rate, mode='view')

@bp_client_user.route('/')
@login_required
def get_orders():
    ''' Orders list for users '''
    return render_template('orders.html')

@bp_client_user.route('/drafts')
@login_required
def get_order_drafts():
    ''' Order drafts list for users '''
    return render_template('order_drafts.html')

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
    order: Order = Order.query.get(order_id)
    if not order:
        abort(Response(f"The order <{order_id}> was not found", status=404))
    if request.values.get('view') == 'print':
        return render_template('order_print_view.html', order=order,
            currency=Currency.query.get('KRW'), rate=1, currencies=[], mode='print',
            language=request.values.get('language') or 'en')

    if request.values.get('view') == 'customs_label':
        return render_template(order.shipping.customs_label_template_name, order=order)
    
    return render_template('new_order.html',
        check_subcustomers=Setting.get('order.new.check_subcustomers'),
        order_id=order_id,
        free_local_shipping_threshold=current_app.config['FREE_LOCAL_SHIPPING_AMOUNT_THRESHOLD'],
        local_shipping_cost=current_app.config['LOCAL_SHIPPING_COST'])


@bp_client_user.route('/<order_id>/excel')
@login_required
def user_get_order_excel(order_id):
    '''
    Generates an Excel file for an order
    '''
    order: Order = Order.query.get(order_id)
    if not order:
        abort(Response(f"The order <{order_id}> was not found", status=404))
    try:
        file = order.get_order_excel()
        return current_app.response_class(stream_and_close(file), headers={
            'Content-Disposition': f'attachment; filename="{order_id}.xlsx"',
            'Content-Type': file_types['xlsx']
        })
    except OrderError as ex:
        abort(Response(
            f"Couldn't generate an order Excel due to following error: {';'.join(ex.args)}"))

@bp_client_admin.route('/<order_id>/customs_label')
@roles_required('admin')
def admin_get_customs_label(order_id):
    '''
    Generates a label for a destination customs for an order
    '''
    order = Order.query.get(order_id)
    if not order:
        abort(Response(f"The order <{order_id}> was not found", status=404))
    try:
        file, ext = order.get_customs_label()
        if file is None:
            raise OrderError("There is no customs label template for this order")
        file.seek(0)
        return current_app.response_class(stream_and_close(file), headers={
            'Content-Disposition': f'attachment; filename="{order_id}_customs_label.{ext}"',
            'Content-Type': file_types[ext]
        })
    except OrderError as ex:
        abort(Response(
            f"Couldn't generate customs label due to following error: {';'.join(ex.args)}"))

@bp_client_admin.route('/subcustomers')
@roles_required('admin')
def admin_get_subcustomers():
    return render_template('admin_subcustomers.html')
