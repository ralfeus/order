'''Client routes for weight based shipping'''
from flask import render_template
from flask_security import roles_required

from .. import bp_client_admin

@bp_client_admin.route('/')
@roles_required('admin')
def admin_edit_shipping_method():
    return render_template('admin_edit_dhl_rates.html')
