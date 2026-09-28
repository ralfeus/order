from app.shipping.models.shipping import Shipping
from datetime import datetime
from decimal import Decimal
import os

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db
from app.models.file import File
from app.products import bp_api_admin, bp_api_user
from app.products.models import Product
from app.tools import get_products_path, modify_object, \
    prepare_datatables_query, write_to_file

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
IMAGE_MAX_SIZE = 5 * 1024 * 1024


@bp_api_user.route('', defaults={'product_id': None})
@bp_api_user.route('/<product_id>')
@login_required
def get_product(product_id):
    '''Returns list of products in JSON'''
    products = None
    error_message = None
    if product_id:
        error_message = f"No product with code <{product_id}> was found"
        stripped_id = product_id.lstrip('0')
        products = Product.query.filter(Product.id.endswith(stripped_id))
        products = [product for product in products
                    if product.id.lstrip('0') == stripped_id]
    else:
        error_message = "There are no products in store now"
        products = Product.query.all()
    if len(products) != 0:
        return jsonify([product.to_dict(details=False) for product in products])
    abort(Response(error_message, status=404))


@bp_api_user.route('/catalog')
@login_required
def get_catalog():
    '''Returns available products for the end-user catalog.
    Prices are in base currency, weight in grams'''
    products = Product.query.filter_by(available=True)
    return jsonify([{
        'id': product.id,
        'name': product.name_english or product.name,
        'image': product.to_dict()['image'],
        'price': product.price or 0,
        'weight': product.weight or 0
    } for product in products])


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
@login_required
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
    if request.values.get('draw') is not None:  # Args were provided by DataTables
        return _filter_products(products, request.values)
    if request.values.get('initialValue') is not None:
        sub = db.session.get(Product, request.values.get('value')[1:-1])
        return jsonify(
            {'id': sub.id, 'text': sub.name}
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
@login_required
@roles_required('admin')
def save_product(product_id):
    '''Saves updates in product or creates new product'''
    payload = request.get_json()
    if product_id is None:
        if not payload.get('id'):
            abort(Response('No product ID is provided', status=400))
        else:
            product_id = payload['id']

    product = db.session.get(Product, product_id)
    if not product:
        product = Product()
        product.id = product_id
        db.session.add(product)
    if 'shipping' in payload.keys():
        product.available_shipping = []
        if len(payload['shipping']) < Shipping.query.count():
            product.available_shipping = \
                Shipping.query.filter(Shipping.id.in_(payload['shipping'])).all()
    editable_attributes = ['name', 'name_english', 'name_russian', 'price',
                           'points', 'weight', 'available', 'separate_shipping',
                           'synchronize', 'purchase', 'color']
    modify_object(product, payload, editable_attributes)

    db.session.commit()

    return jsonify(product.to_dict(details=True))


@bp_api_admin.route('/<product_id>/image', methods=['POST'])
@login_required
@roles_required('admin')
def upload_product_image(product_id):
    '''Sets product image from uploaded file. Previous image file is kept'''
    product = db.session.get(Product, product_id)
    if product is None:
        abort(Response(f"No product with code <{product_id}> was found", status=404))
    file = request.files.get('file')
    if file is None or not file.filename:
        abort(Response('No file is uploaded', status=400))
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        abort(Response(
            f"Unsupported image type <{ext}>. Allowed: "
            f"{', '.join(sorted(IMAGE_EXTENSIONS))}", status=400))
    image_data = file.stream.read(IMAGE_MAX_SIZE + 1)
    if len(image_data) > IMAGE_MAX_SIZE:
        abort(Response('Image is larger than 5 MB', status=413))
    file_name = f"{product_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
    write_to_file(get_products_path(file_name), image_data)
    product.image = File(file_name=file.filename, path=f'/products/{file_name}')
    product.when_changed = datetime.now()
    db.session.commit()
    return jsonify(product.to_dict(details=True))


@bp_api_admin.route('/<product_id>/image', methods=['DELETE'])
@login_required
@roles_required('admin')
def delete_product_image(product_id):
    '''Removes image from product. Image file is kept'''
    product = db.session.get(Product, product_id)
    if product is None:
        abort(Response(f"No product with code <{product_id}> was found", status=404))
    product.image = None
    product.when_changed = datetime.now()
    db.session.commit()
    return jsonify(product.to_dict(details=True))


@bp_api_admin.route('/<product_id>', methods=['DELETE'])
@login_required
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
