''' Client routes for warehouse related activities '''
from flask import abort, render_template, send_file
from flask_security import login_required, roles_required

from app.modules.warehouse import bp_client_admin

@bp_client_admin.route('/static/<path:file>')
def get_static(file):
    '''Returns static files for warehouse module'''
    return send_file(f"modules/warehouse/static/{file}")

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def admin_get_warehouses():
    '''Warehouse management'''
    return render_template('admin_warehouses.html')

@bp_client_admin.route('/<warehouse_id>')
@login_required
@roles_required('admin')
def admin_get_warehouse(warehouse_id):
    '''Warehouse products management'''
    from app.modules.warehouse.models import Warehouse
    warehouse = Warehouse.query.get(warehouse_id)
    if warehouse is None:
        abort(404)
    return render_template('admin_warehouse_products.html', warehouse=warehouse)
