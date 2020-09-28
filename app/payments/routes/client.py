from datetime import datetime
import os.path

from flask import current_app, flash, redirect, request, render_template, \
    send_file
from flask_security import current_user, login_required, roles_required

from app import db
from app.currencies.models import Currency
from app.orders.models import Order
from app.payments import bp_client_admin, bp_client_user
from app.payments.models import Transaction, TransactionStatus
from app.payments.forms.transaction import TransactionForm

from app.tools import write_to_file

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"payments/static/{file}")

@bp_client_admin.route('/')
@roles_required('admin')
def admin_transactions():
    '''
    Transactions management
    '''
    return render_template('admin_transactions.html')

@bp_client_user.route('/')
@login_required
def user_transactions():
    return render_template('transactions.html', balance=current_user.balance)

@bp_client_user.route('/new', methods=['GET', 'POST'])
@login_required
def create_transaction():
    '''
    Creates new transaction request
    '''
    form = TransactionForm()
    form.currency_code.choices = [
        (currency.code, currency.name) for currency in Currency.query.all()]
    form.order_id.choices = [('None', '-- None --')] + \
        [(order.id,order.id) for order in Order.query.filter_by(user=current_user)]
    file_name = ''
    if form.validate_on_submit():
        if form.evidence.data:
            image_data = request.files[form.evidence.name].read()
            file_name = os.path.join(
                current_app.config['UPLOAD_PATH'],
                str(current_user.id),
                datetime.now().strftime('%Y-%m-%d.%H%M%S.%f')) + \
                ''.join(os.path.splitext(form.evidence.data.filename)[1:])
            write_to_file(file_name, image_data)

        currency = Currency.query.get(form.currency_code.data)
        new_transaction = Transaction(
            user=current_user,
            amount_sent_original=form.amount_original.data,
            currency=currency,
            amount_sent_krw=form.amount_original.data / currency.rate,
            amount_received_krw=form.amount_original.data / currency.rate,
            payment_method=form.payment_method.data,
            order_id=form.order_id.data if form.order_id.data != 'None' else None,
            proof_image=file_name,
            status=TransactionStatus.pending,
            when_created=datetime.now())

        db.session.add(new_transaction)
        try:
            db.session.commit()
            flash("The transaction is created", category='info')
            return redirect('/wallet')
        except Exception as e:
            flash(f"The transaction couldn't be created. {e}", category="error")
    return render_template('transaction.html', title="Create transaction", form=form)
