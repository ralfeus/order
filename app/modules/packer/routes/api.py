'''API routes for warehouse module'''
from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, roles_required

from app import db
from app.modules.packer.models.order_packer import OrderPacker
from app.modules.packer.validators.order_packer import OrderPackerValidator
from app.orders.models.order import Order
from app.tools import modify_object, prepare_datatables_query

from app.modules.packer import bp_api_admin

@bp_api_admin.route('')
@roles_required('admin')
def admin_get_warehouses():
    ''' Returns all or selected warehouses in JSON '''
    orders = Order.query
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_objects(orders, request.values)

    return jsonify({'data': [entry.to_dict(details=True, partial=['id', 'packer']) for entry in orders]})

@bp_api_admin.route('/<order_id>', methods=['POST'])
@roles_required('admin')
def admin_save_order_packer(order_id):
    '''Modify the warehouse'''
    logger = current_app.logger.getChild('admin_save_warehouse')
    order_packer = OrderPacker.query.get(order_id)
    if not order_packer:
        abort(Response(f'No order {order_id} was found', status=404))
    with OrderPackerValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't edit an order packer",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    payload = request.get_json()
    logger.info('Modifying order packer %s by %s with data: %s',
                order_id, current_user, payload)
    modify_object(order_packer, payload, ['name'])
    db.session.commit()
    return jsonify({'data': [order_packer.to_dict()]})

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
