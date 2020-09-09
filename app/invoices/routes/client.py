from flask import Blueprint, Response, abort, render_template
from flask_security import roles_required

from app.invoices import bp_client_admin, bp_client_user
from app.models import Invoice, InvoiceItem

@bp_client_admin.route('/<invoice_id>')
@roles_required('admin')
def get_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(Response(f"No invoice {invoice_id} was found", status=404))
    return render_template('invoice.html', context=invoice.to_dict())
