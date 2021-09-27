''' Client routes for finance management '''
from flask import render_template, send_file
from flask_security import current_user, login_required, roles_required
from flask.globals import current_app
import json

from app.payments import bp_client_admin, bp_client_user
# from app.payments.models import Payment


@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"payments/static/{file}")

@bp_client_admin.route('/balances')
@roles_required('admin')
def admin_balances():
    ''' Customers balances '''
    return render_template('admin_balances.html')

@bp_client_admin.route('/methods')
@roles_required('admin')
def admin_payment_methods():
    ''' Payment methods management '''
    return render_template('admin_payment_methods.html')

@bp_client_admin.route('/')
@roles_required('admin')
def admin_payments():
    '''
    Payments management
    '''
    return render_template('admin_payments.html')

@bp_client_admin.route('/transactions')
@roles_required('admin')
def admin_transactions():
    '''
    Payments management
    '''
    return render_template('admin_transactions.html')

@bp_client_user.route('/')
@login_required
def user_wallet():
    return render_template('wallet.html', balance=current_user.balance)
