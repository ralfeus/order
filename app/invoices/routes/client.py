from flask import Blueprint, render_template
from flask_security import roles_required

from app.invoices import bp_client_admin, bp_client_user

@bp_client_admin.route('/<invoice_id>')
@roles_required('admin')
def get_invoice(invoice_id):
    return render_template('invoice.html')
