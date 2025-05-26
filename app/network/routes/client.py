'''Network management client routes'''
from flask import render_template, send_file
from flask_security import login_required, roles_required

from app.network import bp_client_admin

@bp_client_admin.route('/static/<path:file>')
def get_static(file):
    '''Access to static files'''
    return send_file(f"network/static/{file}")

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def admin_get_network():
    '''Network management'''
    return render_template('admin_network.html')
