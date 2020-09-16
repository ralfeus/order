from flask import Response, abort, render_template, send_file
from flask_security import roles_required

from app.currencies.models import Currency
from app.currencies import bp_client_admin, bp_client_user
# from app.invoices.models import Invoice

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"invoices/static/{file}")

@bp_client_admin.route('/<currency_id>')
@roles_required('admin')
def get_currency(currency_id):
    currency = Currency.query.get(currency_id)
    if not currency:
        abort(Response(f"No currency {currency_id} was found", status=404))

    usd_rate = Currency.query.get('USD').rate
    return render_template('currency.html', context=currency.to_dict(), usd_rate=usd_rate)

@bp_client_admin.route('/')
@roles_required('admin')
def get_currencies():
    '''
    Currency management
    '''
    usd_rate = Currency.query.get('USD').rate
    
    return render_template('currency.html', usd_rate=usd_rate)
