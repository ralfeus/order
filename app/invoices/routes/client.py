from flask import Response, abort, render_template, send_file
from flask_login import current_user
from flask_security import login_required, roles_required

from app.currencies.models import Currency
from app.invoices import bp_client_admin, bp_client_user
from app.invoices.models import Invoice

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"invoices/static/{file}")

@bp_client_admin.route('/<invoice_id>')
@login_required
@roles_required('admin')
def admin_get_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(Response(f"No invoice {invoice_id} was found", status=404))

    usd_rate = Currency.query.get('USD').rate
    return render_template('admin_invoice.html', context=invoice, usd_rate=usd_rate)


@bp_client_user.route('/<invoice_id>')
@login_required
def get_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(Response(f"No invoice {invoice_id} was found", status=404))
    if invoice.user != current_user:
        abort(Response(f"No invoice {invoice_id} was found", status=404))
    usd_rate = Currency.query.get('USD').rate
    return render_template('invoice.html', context=invoice, usd_rate=usd_rate)

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def admin_get_invoices():
    '''
    Invoice management for admins
    '''
    usd_rate = Currency.query.get('USD').rate
    
    return render_template('admin_invoices.html', usd_rate=usd_rate)

@bp_client_user.route('/')
@login_required
def get_invoices():
    '''
    Invoice management for users
    '''
    usd_rate = Currency.query.get('USD').rate
    
    return render_template('invoices.html', usd_rate=usd_rate)
