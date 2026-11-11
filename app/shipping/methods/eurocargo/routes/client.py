'''Admin client routes for EurocargoShipping'''
from flask import render_template
from flask_security import login_required, roles_required

from app import db

from .. import bp_client_admin
from ..models.eurocargo_shipping import EurocargoShipping


@bp_client_admin.route('/<int:shipping_id>')
@login_required
@roles_required('admin')
def admin_edit(shipping_id):
    shipping = db.session.get(EurocargoShipping, shipping_id)
    return render_template('admin_edit_eurocargo.html', shipping=shipping)
