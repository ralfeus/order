from flask import jsonify, request
from flask_security import roles_required

from app import db
from app.network.models.node import Node
from app.network import bp_api_admin
from app.tools import prepare_datatables_query

@bp_api_admin.route('', defaults={'node_id': None})
@bp_api_admin.route('/<int:node_id>')
@roles_required('admin')
def admin_get_nodes(node_id):
    '''
    Returns all or selected nodes in JSON
    '''
    nodes = Node.query
    if node_id is not None:
        nodes = nodes.filter_by(id=node_id)
        
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_nodes(nodes, request.values)


    return jsonify(list(map(lambda entry: entry.to_dict(), nodes)))

def _filter_nodes(nodes, filter_params):
    nodes, records_total, records_filtered = prepare_datatables_query(
        nodes, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': list(map(lambda entry: entry.to_dict(), nodes))
    })
