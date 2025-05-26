from flask import render_template, send_file
from flask_security import login_required, roles_required

from app.shipping import bp_client_admin

@bp_client_admin.route('/static/<path:file>')
def get_static(file):
    return send_file(f"shipping/static/{file}")

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def admin_shipping_methods():
    return render_template('admin_shipping_methods.html')
