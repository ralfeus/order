''' Client routes for Packer related activities '''
from flask import render_template, send_file
from flask_security import roles_required

from app.modules.packer import bp_client_admin

@bp_client_admin.route('/static/<path:file>')
def get_static(file):
    '''Returns static files for packer module'''
    return send_file(f"modules/packer/static/{file}")

@bp_client_admin.route('/')
@roles_required('admin')
def admin_get_warehouses():
    '''Packer management'''
    return render_template('admin_order_packers.html')
