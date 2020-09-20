'''
Contains admin routes of the application
'''
from flask import Blueprint, Response, abort, current_app, flash, redirect, \
                  render_template, request
from flask_security import current_user, login_required, login_user, roles_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import ProductForm, SignupForm
from app.invoices.models import Invoice
from app.models import Currency, Order, Product, User

admin = Blueprint('admin', __name__, url_prefix='/admin')

@admin.route('/')
@roles_required('admin')
def order_products():
    '''
    Shows list of ordered products
    '''
    return render_template('order_products.html')


@admin.route('/product/new', methods=['GET', 'POST'])
@roles_required('admin')
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
@roles_required('admin')
def products():
    '''
    Product catalog management
    '''
    return render_template('products.html')

@admin.route('/users/new', methods=['GET', 'POST'])
@roles_required('admin')
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
@roles_required('admin')
def users():
    '''
    Edits the user settings
    '''
    return render_template('users.html')
    
@admin.route('/transactions')
@roles_required('admin')
def admin_transactions():
    '''
    Transactions management
    '''
    return render_template('transactions.html')

@admin.route('/orders')
@roles_required('admin')
def admin_orders():
    '''
    Order management
    '''
    usd_rate = Currency.query.get('USD').rate
    return render_template('orders.html', usd_rate=usd_rate)

@admin.route('/orders/<order_id>')
@roles_required('admin')
def get_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        abort(Response("The order <{order_id}> was not found", status=404))
    if request.values.get('view') == 'print':
        return render_template('order_print_view.html', order=order)
    abort(501)
