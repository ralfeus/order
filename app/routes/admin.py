'''
Contains admin routes of the application
'''
from flask import abort, Response, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import flask, db
from app.forms import ProductForm, SignupForm
from app.models import Currency, Invoice, Product, User

@flask.route('/admin')
@login_required
def admin():
    '''
    Shows list of ordered products
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('order_products.html')


@flask.route('/admin/product/new', methods=['GET', 'POST'])
@login_required
def product():
    '''
    Creates and edits product
    '''
    form = ProductForm()
    if form.validate_on_submit():
        new_product = Product()
        form.populate_obj(new_product)

        db.session.add(new_product)
        try:
            db.session.commit()
            flash("The product is created", category='info')
            return redirect('/admin/products')
        except IntegrityError as e:
            flash(f"The product couldn't be created. {e}", category="error")
    return render_template('product.html', title="Create product", form=form)

@flask.route('/admin/products')
@login_required
def products():
    '''
    Product catalog management
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('products.html')

@flask.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    '''
    Creates new user
    '''
    userform = SignupForm()
    if userform.validate_on_submit():
        new_user = User()
        userform.populate_obj(new_user)

        db.session.add(new_user)
        return redirect('/admin/users')
    return render_template('signup.html', title="Create user", form=userform)

@flask.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_edit_user():
    '''
    Edits the user settings
    '''
    return render_template('users.html')
    
@flask.route('/admin/transactions')
@login_required
def admin_transactions():
    '''
    Transactions management
    '''
    if current_user.username != 'admin':
        abort(403)
    
    return render_template('transactions.html')

@flask.route('/admin/invoices')
@login_required
def admin_invoices():
    '''
    Invoice management
    '''
    if current_user.username != 'admin':
        abort(403)

    usd_rate = Currency.query.get('USD').rate
    
    return render_template('invoices.html', usd_rate=usd_rate)

@flask.route('/admin/orders')
@login_required
def admin_orders():
    '''
    Order management
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('orders.html')
