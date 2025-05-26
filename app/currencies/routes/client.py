from flask import Response, abort, render_template, send_file
from flask_security import login_required, roles_required

from app.currencies.models import Currency
from app.currencies import bp_client_admin, bp_client_user
# from app.invoices.models import Invoice

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"currencies/static/{file}")

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def get_currencies():
    '''
    Currency management
    '''
    return render_template('currencies.html')
