from flask import render_template, send_file
from flask_security import login_required, roles_required

from app.settings import bp_client_admin

@bp_client_admin.route('/static/<path:file>')
def get_static(file):
    return send_file(f"settings/static/{file}")

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def purchase_orders():
    return render_template('admin_settings.html')
