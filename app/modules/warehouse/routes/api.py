'''API routes for warehouse module'''
from typing import Any
from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.tools import modify_object, prepare_datatables_query

from app.modules.warehouse import bp_api_admin
from app.modules.warehouse.models.warehouse import Warehouse, WarehouseProduct
from app.modules.warehouse.validators.warehouse import WarehouseValidator
from app.modules.warehouse.validators.warehouse_product import WarehouseProductValidator

@bp_api_admin.route('/<warehouse_id>', methods=['DELETE'])
@login_required
@roles_required('admin')
def admin_delete_warehouses(warehouse_id):
    ''' Deletes a warehouses '''
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        abort(Response(f'No warehouse {warehouse_id} was found', status=404))
    db.session.delete(warehouse) #type: ignore
    db.session.commit() #type: ignore
    return jsonify({})

@bp_api_admin.route('', defaults={'warehouse_id': None})
@bp_api_admin.route('/<warehouse_id>')
@login_required
@roles_required('admin')
def admin_get_warehouses(warehouse_id):
    ''' Returns all or selected warehouses in JSON '''
    warehouses = Warehouse.query
    if warehouse_id is not None:
        warehouses = warehouses.filter_by(id=warehouse_id)
        if warehouses.count() == 1:
            return jsonify(warehouses.first().to_dict(details=True))
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_objects(warehouses, request.values)

    return jsonify({'data':
        [entry.to_dict(details=request.values.get('details')) for entry in warehouses]})

@bp_api_admin.route('', defaults={'warehouse_id': None}, methods=['POST'])
@bp_api_admin.route('/<warehouse_id>', methods=['POST'])
@login_required
@roles_required('admin')
def admin_save_warehouse(warehouse_id):
    '''Modify the warehouse'''
    logger = current_app.logger.getChild('admin_save_warehouse')
    if warehouse_id is None:
        warehouse = Warehouse()
        db.session.add(warehouse) #type: ignore
    else:
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            abort(Response(f'No warehouse {warehouse_id} was found', status=404))
    with WarehouseValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't edit a warehouse",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    payload: dict[str, Any] = request.get_json() #type: ignore
    logger.info('Modifying warehouse %s by %s with data: %s',
                warehouse_id, current_user, payload)
    modify_object(warehouse, payload, ['name', 'is_local'])
    db.session.commit() #type: ignore
    return jsonify({'data': [warehouse.to_dict()]})

def _filter_objects(entities, filter_params):
    entities, records_total, records_filtered = prepare_datatables_query(
        entities, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict() for entry in entities]
    })

@bp_api_admin.route('/<warehouse_id>/product', defaults={'product_id': None})
@bp_api_admin.route('/<warehouse_id>/product/<product_id>')
@login_required
@roles_required('admin')
def admin_get_warehouse_products(warehouse_id, product_id):
    ''' Returns all or selected products in a warehouse in JSON '''
    warehouse = Warehouse.query.get(warehouse_id)
    if warehouse is None:
        return jsonify({})
    products = warehouse.products if product_id is None \
        else warehouse.products.filter_by(product_id=product_id)
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_objects(products, request.values)

    return jsonify({'data': [entry[1].to_dict() for entry in products.col.items()]})

@bp_api_admin.route('/<warehouse_id>/product', defaults={'product_id': None}, methods=['POST'])
@bp_api_admin.route('/<warehouse_id>/product/<product_id>', methods=['POST'])
@login_required
@roles_required('admin')
def admin_save_warehouse_product(warehouse_id, product_id):
    '''Creates or saves existing warehouse product'''
    logger = current_app.logger.getChild('admin_save_warehouse_product')
    warehouse = Warehouse.query.get(warehouse_id)
    if warehouse is None:
        return jsonify({
                'data': [],
                'error': "Couldn't edit a warehouse product. No warehouse found"
        })
            
    with WarehouseProductValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't edit a warehouse",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    payload: dict[str, Any] = request.get_json() #type: ignore
    if product_id is None:
        product = WarehouseProduct(warehouse_id=warehouse_id, product_id=payload['product_id'])
        db.session.add(product) #type: ignore
    else:
        product = WarehouseProduct.query.filter_by(
            warehouse_id=warehouse_id, product_id=product_id).first()
    logger.info('Modifying product %s in warehouse %s by %s with data: %s',
                product_id, warehouse_id, current_user, payload)
    modify_object(product, payload, ['quantity'])
    db.session.commit() #type: ignore
    return jsonify({'data': [product.to_dict()]})
    
@bp_api_admin.route('/<warehouse_id>/product/<product_ids>', methods=['DELETE'])
@login_required
@roles_required('admin')
def admin_delete_warehouse_product(warehouse_id, product_ids):
    ''' Deletes a warehouses '''
    warehouse = Warehouse.query.get(warehouse_id)
    if warehouse is None:
        abort(Response(f'No warehouse {warehouse_id} was found', status=404))
    for product_id in product_ids.split(','):
        product = WarehouseProduct.query.filter_by(
            warehouse_id=warehouse_id, product_id=product_id).first()
        if product is None:
            abort(Response(f'No product {product_id} in warehouse {warehouse_id} was found',
                status=404))
        db.session.delete(product) #type: ignore
    db.session.commit() #type: ignore
    return jsonify({})
