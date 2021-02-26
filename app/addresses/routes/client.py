from flask import Response, abort, render_template, send_file
from flask_security import roles_required

from app.models.address import Address
from app.addresses import bp_client_admin, bp_client_user
# from app.invoices.models import Invoice

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"addresses/static/{file}")

@bp_client_admin.route('/')
@roles_required('admin')
def get_addresses():
    '''
    Currency management
    '''
    return render_template('addresses.html')
