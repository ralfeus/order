'''Client routes for weight based shipping'''
import os.path
from flask import render_template, send_file
from flask_security import roles_required

from app.shipping.models import Shipping

from .. import bp_client_admin

@bp_client_admin.route('/static/<path:file>')
def get_static(file):
    return send_file(f"{os.path.dirname(__file__)}/{os.path.pardir}/static/{file}")

@bp_client_admin.route('/<shipping_id>')
@roles_required('admin')
def admin_edit_shipping_method(shipping_id):
    return render_template('admin_edit_rates.html', shipping=Shipping.query.get(shipping_id))
