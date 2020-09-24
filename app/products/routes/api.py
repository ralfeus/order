from datetime import datetime
from decimal import Decimal

from flask import Response, abort, jsonify, request
from flask_security import current_user, login_required, roles_required

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db
from app.models import Currency, Shipping
from app.products import bp_api_admin, bp_api_user
from app.orders.models import Order, OrderProduct, OrderProductStatusEntry, \
    Suborder, Subcustomer
from app.products.models import Product


@bp_api_user.route('/', defaults={'product_id': None}, strict_slashes=False)
@bp_api_user.route('/<product_id>')
@login_required
def get_product(product_id):
    '''
    Returns list of products in JSON
    '''
    product_query = None
    error_message = None
    if product_id:
        error_message = f"No product with code <{product_id}> was found"
        stripped_id = product_id.lstrip('0')
        product_query = Product.query.filter_by(available=True). \
            filter(Product.id.endswith(stripped_id)).all()
        product_query = [product for product in product_query
                        if product.id.lstrip('0') == stripped_id]
    else:
        error_message = "There are no available products in store now"
        product_query = Product.query.filter_by(available=True).all()
    if len(product_query) != 0:
        return jsonify(Product.get_products(product_query))
    abort(Response(error_message, status=404))

@bp_api_user.route('/search/<term>')
@login_required
def get_product_by_term(term):
    '''
    Returns list of products where product ID or name starts with provided value in JSON
    '''
    product_query = Product.query.filter_by(available=True).filter(or_(
        Product.id.like(term + '%'),
        Product.name.like(term + '%'),
        Product.name_english.like(term + '%'),
        Product.name_russian.like(term + '%')))
    return jsonify(Product.get_products(product_query))


@bp_api_admin.route('/', defaults={'product_id': None}, strict_slashes=False)
@bp_api_admin.route('/<product_id>')
@roles_required('admin')
def admin_get_product(product_id):
    '''
    Returns list of products in JSON
    '''
    product_query = None
    if product_id:
        product_query = Product.query.filter_by(id=product_id)
    else:
        product_query = Product.query.all()
    return jsonify(Product.get_products(product_query))

@bp_api_admin.route('/', defaults={'product_id': None}, methods=['POST'], strict_slashes=False)
@bp_api_admin.route('/<product_id>', methods=['POST'])
@roles_required('admin')
def save_product(product_id):
    '''
    Saves updates in product or creates new product
    '''
    payload = request.get_json()
    if product_id is None:
        if not payload.get('id'):
            abort(Response('No product ID is provided', status=400))
        else:
            product_id = payload['id']

    product = Product.query.get(product_id)
    if not product:
        product = Product()
        product.id = product_id
        db.session.add(product)

    editable_attributes = ['name', 'name_english', 'name_russian', 'price',
                           'points', 'weight', 'available', 'synchronize']
    for attr in editable_attributes:
        if payload.get(attr) is not None:
            setattr(product, attr, payload[attr])
            product.when_changed = datetime.now()

    db.session.commit()

    return jsonify(product.to_dict())

@bp_api_admin.route('/<product_id>', methods=['DELETE'])
@roles_required('admin')
def delete_product(product_id):
    '''
    Deletes a product by its product code
    '''
    result = None
    try:
        Product.query.filter_by(id=product_id).delete()
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete product {product_id} as it's used in some orders"
        })
        result.status_code = 409

    return result
