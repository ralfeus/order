from app.shipping.models.shipping import Shipping
from datetime import datetime
from decimal import Decimal

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db
from app.products import bp_api_admin, bp_api_user
from app.products.models import Product
from app.tools import modify_object, prepare_datatables_query

@bp_api_user.route('', defaults={'product_id': None})
@bp_api_user.route('/<product_id>')
@login_required
def get_product(product_id):
    '''Returns list of products in JSON'''
    product_query = None
    error_message = None
    if product_id:
        error_message = f"No product with code <{product_id}> was found"
        stripped_id = product_id.lstrip('0')
        product_query = Product.query.filter(Product.id.endswith(stripped_id))
        product_query = [product for product in product_query
                        if product.id.lstrip('0') == stripped_id]
    else:
        error_message = "There are no products in store now"
        product_query = Product.query.all()
    if len(product_query) != 0:
        return jsonify([product.to_dict(details=False) for product in product_query])
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
    return jsonify([product.to_dict(details=False) for product in product_query])


@bp_api_admin.route('', defaults={'product_id': None})
@bp_api_admin.route('/<product_id>')
@roles_required('admin')
def admin_get_product(product_id):
    '''
    Returns list of products in JSON
    '''
    products = None
    if product_id:
        products = Product.query.filter_by(id=product_id)
    else:
        products = Product.query
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_products(products, request.values)
    if request.values.get('initialValue') is not None:
        sub = Product.query.get(request.values.get('value'))
        return jsonify(
            {'id': sub.id, 'text': sub.name} \
                if sub is not None else {})
    if request.values.get('q') is not None:
        products = products.filter(or_(
            Product.id.like(f'%{request.values["q"]}%'),
            Product.name.like(f'%{request.values["q"]}%')
        ))
    if request.values.get('page') is not None:
        page = int(request.values['page'])
        total_results = products.count()
        products = products.offset((page - 1) * 100).limit(page * 100)
        return jsonify({
            'results': [entry.to_dict() for entry in products],
            'pagination': {
                'more': total_results > page * 100
            }
        })

    return jsonify([product.to_dict(details=False) for product in products])

def _filter_products(products, filter_params):
    products, records_total, records_filtered = prepare_datatables_query(
        products, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict(details=True) for entry in products]
    })

@bp_api_admin.route('', defaults={'product_id': None}, methods=['POST'])
@bp_api_admin.route('/<product_id>', methods=['POST'])
@roles_required('admin')
def save_product(product_id):
    '''Saves updates in product or creates new product'''
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
    if 'shipping' in payload.keys():
        product.available_shipping = []
        if len(payload['shipping']) < Shipping.query.count():
            product.available_shipping = \
                Shipping.query.filter(Shipping.id.in_(payload['shipping']))
    editable_attributes = ['name', 'name_english', 'name_russian', 'price',
                           'points', 'weight', 'available', 'separate_shipping',
                           'synchronize', 'purchase', 'color']
    modify_object(product, payload, editable_attributes)

    db.session.commit()

    return jsonify(product.to_dict(details=True))

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
