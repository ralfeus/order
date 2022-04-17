import itertools
from flask import render_template, send_file
from flask_security import roles_required

from app.purchase import bp_client_admin, bp_client_user

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"purchase/static/{file}")

@bp_client_admin.route('/orders')
@roles_required('admin')
def purchase_orders():
    from app.purchase.signals import create_purchase_order_rendering
    extensions = create_purchase_order_rendering.send()
    extension_columns = list(itertools.chain(*[
        extension[1]['columns'] for extension in extensions]))
    return render_template('purchase_orders.html', ext_columns=extension_columns)

@bp_client_admin.route('/dynamic/purchase_orders.js')
def get_admin_purchase_orders_js():
    from app.purchase.signals import create_purchase_order_rendering
    extensions = create_purchase_order_rendering.send()
    extension_fields = list(itertools.chain(*[
        extension[1]['fields'] for extension in extensions]))
    extension_columns = list(itertools.chain(*[
        extension[1]['columns'] for extension in extensions]))
    return render_template('purchase_orders.js', extension={
        'fields': extension_fields,
        'columns': extension_columns
    })


@bp_client_admin.route('/companies')
@roles_required('admin')
def get_company():
    ''' company management '''
    return render_template('companies.html')