from flask import Response, abort, escape, request, render_template, send_file
from flask_security import roles_required

from app.purchase import bp_client_admin, bp_client_user

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"purchase/static/{file}")
