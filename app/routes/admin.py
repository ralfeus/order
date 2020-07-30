'''
Contains admin routes of the application
'''
from flask import abort, Response, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.forms import ProductForm, SignupForm
from app.models import Product, User

@app.route('/admin')
<<<<<<< HEAD
=======
@login_required
>>>>>>> master
def admin():
    '''
    Shows list of ordered products
    '''
<<<<<<< HEAD
    if current_user.is_anonymous:
        result = Response('Anonymous access is denied', mimetype='text/html')
        result.status_code = 401
        return result
=======
    if current_user.username != 'admin':
        abort(403)
>>>>>>> master

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

<<<<<<< HEAD
@app.route('/admin/user/new', methods=['GET', 'POST'])
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
    return render_template('signup.html', title="Create user", form=userform)
    return redirect('/admin/users')

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_edit_user():
    '''
    Edits the user settings
    '''
    return render_template('users.html')
=======
@app.route('/admin/transactions')
@login_required
def admin_transactions():
    '''
    Transactions management
    '''
    if current_user.username != 'admin':
        abort(403)
    
    return render_template('transactions.html')
>>>>>>> master
