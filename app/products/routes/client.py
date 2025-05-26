from flask import Response, abort, current_app, escape, redirect, request, \
     render_template, send_file, send_from_directory, flash, url_for
from flask_security import login_required, roles_required

from sqlalchemy.exc import IntegrityError

from app import db

from app.products import bp_client_admin, bp_client_user
# from app.products.forms.product import ProductForm
from app.products.models import Product

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"products/static/{file}")

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def get_products():
    '''
    Product catalog management
    '''
    return render_template('products.html')
