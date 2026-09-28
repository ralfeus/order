from flask import Response, abort, current_app, escape, redirect, request, \
     render_template, send_file, send_from_directory, flash, url_for
from flask_security import current_user, login_required, roles_required

from sqlalchemy.exc import IntegrityError

from app import db

from app.currencies.models import Currency
from app.models import Country
from app.products import bp_client_admin, bp_client_catalog, bp_client_user
from app.shipping.methods.ems.models.ems import EMS
# from app.products.forms.product import ProductForm
from app.products.models import Product

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"products/static/{file}")

@bp_client_catalog.route('')
@login_required
def get_catalog():
    '''
    Product catalog for end users
    '''
    tenant = current_app.config.get('TENANT_NAME', 'default')
    user_currency = db.session.get(Currency, current_user.currency_code) \
        if current_user.currency_code else Currency.get_base_currency(tenant)
    ems = EMS.query.filter_by(enabled=True).first()
    profile = current_user.get_profile()
    return render_template('catalog.html',
        base_country=Country.get_base_country(tenant),
        user_currency=user_currency,
        ems_shipping_id=ems.id if ems else None,
        catalog_country=profile.get('catalog_country'),
        catalog_markup=profile.get('catalog_markup', 1))

@bp_client_admin.route('/')
@login_required
@roles_required('admin')
def get_products():
    '''
    Product catalog management
    '''
    return render_template('products.html')
