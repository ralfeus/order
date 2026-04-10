'''Admin client routes for SeparateShipping'''
from flask import render_template
from flask_security import login_required, roles_required

from app import db

from .. import bp_client_admin
from ..models.separate_shipping import SeparateShipping


@bp_client_admin.route('/<int:shipping_id>')
@login_required
@roles_required('admin')
def admin_edit(shipping_id):
    shipping = db.session.get(SeparateShipping, shipping_id)
    return render_template('admin_edit_separate.html', shipping=shipping)
