'''
Contains admin routes of the application
'''
from flask import abort, Response, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.forms import ProductForm
from app.models import Product, User

@app.route('/admin')
@login_required
def admin():
    '''
    Shows list of ordered products
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('order_products.html')


@app.route('/admin/product/new', methods=['GET', 'POST'])
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

@app.route('/admin/products')
@login_required
def products():
    '''
    Product catalog management
    '''
    if current_user.username != 'admin':
        abort(403)

    return render_template('products.html')

@app.route('/admin/transactions')
@login_required
def admin_transactions():
    '''
    Transactions management
    '''
    if current_user.username != 'admin':
        abort(403)
    
    return render_template('transactions.html')