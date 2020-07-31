'''
Contains admin routes of the application
'''
from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import ProductForm
from app.models import Product, User

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

@admin.route('/transactions')
@login_required
def admin_transactions():
    '''
    Transactions management
    '''
    if current_user.username != 'admin':
        abort(403)
    
    return render_template('transactions.html')