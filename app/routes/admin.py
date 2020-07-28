'''
Contains admin routes of the application
'''
from flask import Response, flash, redirect, render_template
from flask_login import current_user, login_required, login_user
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.forms import ProductForm, SignupForm
from app.models import Product, User

@app.route('/admin')
def admin():
    '''
    Shows list of ordered products
    '''
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
    return render_template('products.html')

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

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_edit_user():
    '''
    Edits the user settings
    '''
    return render_template('users.html')

@app.route('/admin/users/delete', methods=['DELETE'])
@login_required
def delete_user(user_id):
    '''
    Deletes, edits and disables a user by its user code
    '''
    result = None
    try:
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete user {user_id} as it's used in some orders"
        })
        result.status_code = 409

    return result

