''' Notifications client routes '''
from flask import render_template, send_file
from flask_security.decorators import roles_required

from .. import bp_client_admin, bp_client_user

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"notifications/static/{file}")

@bp_client_admin.route('/')
@roles_required('admin')
def get_notifications():
    return render_template('admin_notifications.html')
