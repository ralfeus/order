from flask import Response, abort, current_app, escape, redirect, request, \
     render_template, send_file, send_from_directory, flash, url_for
from flask_security import roles_required

from sqlalchemy.exc import IntegrityError

from app import db

from app.products import bp_client_admin, bp_client_user
from app.products.forms.product import ProductForm
from app.products.models import Product

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"products/static/{file}")

@bp_client_admin.route('/')
@roles_required('admin')
def get_products():
    '''
    Product catalog management
    '''
    return render_template('products.html')

@bp_client_admin.route('/new', methods=['GET', 'POST'])
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
        except IntegrityError as ex:
            flash(f"The product couldn't be created. {ex}", category="error")
    return render_template('product.html', title="Create product", form=form)
