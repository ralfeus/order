'''
Contains admin routes of the application
'''
from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import ProductForm, SignupForm
from app.models import Currency, Invoice, Product, User

admin = Blueprint('admin', __name__, url_prefix='/admin')

@admin.route('/')
@login_required
def order_products():
    '''
    Shows list of ordered products
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('order_products.html')


@admin.route('/product/new', methods=['GET', 'POST'])
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

@admin.route('/products')
@login_required
def products():
    '''
    Product catalog management
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('products.html')

@admin.route('/users/new', methods=['GET', 'POST'])
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

@admin.route('/users', methods=['GET', 'POST'])
@login_required
def admin_edit_user():
    '''
    Edits the user settings
    '''
    return render_template('users.html')
    
@admin.route('/transactions')
@login_required
def admin_transactions():
    '''
    Transactions management
    '''
    if current_user.username != 'admin':
        abort(403)
    
    return render_template('transactions.html')

@admin.route('/invoices')
@login_required
def admin_invoices():
    '''
    Invoice management
    '''
    if current_user.username != 'admin':
        abort(403)

    usd_rate = Currency.query.get('USD').rate
    
    return render_template('invoices.html', usd_rate=usd_rate)

@admin.route('/orders')
@login_required
def admin_orders():
    '''
    Order management
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('orders.html')
