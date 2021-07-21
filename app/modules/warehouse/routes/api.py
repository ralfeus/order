'''API routes for warehouse module'''
from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, roles_required

from app import db
from app.tools import modify_object, prepare_datatables_query

from app.modules.warehouse import bp_api_admin
from app.modules.warehouse.models.warehouse import Warehouse
from app.modules.warehouse.validators.warehouse import WarehouseValidator

@bp_api_admin.route('/<warehouse_id>', methods=['DELETE'])
@roles_required('admin')
def admin_delete_warehouses(warehouse_id):
    ''' Deletes a warehouses '''
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        abort(Response(f'No warehouse {warehouse_id} was found', status=404))
    db.session.delete(warehouse)
    db.session.commit()
    return jsonify({})

@bp_api_admin.route('', defaults={'warehouse_id': None})
@bp_api_admin.route('/<warehouse_id>')
@roles_required('admin')
def admin_get_warehouses(warehouse_id):
    ''' Returns all or selected warehouses in JSON '''
    warehouses = Warehouse.query
    if warehouse_id is not None:
        warehouses = warehouses.filter_by(id=warehouse_id)
        if warehouses.count() == 1:
            return jsonify(warehouses.first().to_dict(details=True))
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_warehouses(warehouses, request.values)

    return jsonify({'data':
        [entry.to_dict(details=request.values.get('details')) for entry in warehouses]})

@bp_api_admin.route('', defaults={'warehouse_id': None}, methods=['POST'])
@bp_api_admin.route('/<warehouse_id>', methods=['POST'])
@roles_required('admin')
def admin_save_warehouse(warehouse_id):
    '''Modify the warehouse'''
    logger = current_app.logger.getChild('admin_save_warehouse')
    if warehouse_id is None:
        warehouse = Warehouse()
        db.session.add(warehouse)
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
    payload = request.get_json()
    logger.info('Modifying warehouse %s by %s with data: %s',
                warehouse_id, current_user, payload)
    modify_object(warehouse, payload, ['name', 'is_local'])
    db.session.commit()
    return jsonify({'data': [warehouse.to_dict()]})

def _filter_warehouses(warehouses, filter_params):
    warehouses, records_total, records_filtered = prepare_datatables_query(
        warehouses, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict() for entry in warehouses]
    })
