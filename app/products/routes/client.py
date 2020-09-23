from flask import Response, abort, current_app, escape, request, render_template, \
     send_file, send_from_directory, flash, url_for
from flask_security import current_user, login_required, roles_required

from app.orders import bp_client_admin, bp_client_user

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"products/static/{file}")

