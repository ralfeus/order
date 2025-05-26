'''Client routes for weight based shipping'''
from flask import render_template
from flask_security import login_required, roles_required

from app.shipping.models.shipping import Shipping

from .. import bp_client_admin

@bp_client_admin.route('/<shipping_id>')
@login_required
@roles_required('admin')
def admin_edit_shipping_method(shipping_id):
    return render_template('admin_edit_weight_based_rates.html',
        shipping=Shipping.query.get(shipping_id))
