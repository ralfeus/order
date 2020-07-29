'''
Contains admin routes of the application
'''
from flask import abort, Response, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.forms import ProductForm
from app.models import Product, User

@app.route('/admin', defaults={'key': None})
@app.route('/admin/<key>')
def admin(key):
    '''
    Shows list of ordered products
    '''
    if key == app.config['ADMIN_HASH']:
        login_user(User(id=0), remember=True)
    if current_user.is_anonymous:
        result = Response('Anonymous access is denied', mimetype='text/html')
        result.status_code = 401
        return result

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