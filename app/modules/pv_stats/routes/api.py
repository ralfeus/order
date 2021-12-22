'''API routes for warehouse module'''
from itertools import zip_longest
import json
import requests

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.settings.models import Setting
from app.tools import prepare_datatables_query

from .. import bp_api_admin, bp_api_user
from ..models import PVStatsPermissions


def _filter_nodes(nodes, filter_params):
    nodes, records_total, records_filtered = prepare_datatables_query(
        nodes, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict() for entry in nodes]
    })

@bp_api_user.route('', methods=['POST'])
@login_required
def user_create_pv_stat_node():
    payload = request.get_json()
    if payload.get('node_id') is None:
        abort(400)
    node = PVStatsPermissions(
        user_id=current_user.id,
        node_id=payload['node_id'],
        allowed=current_user.has_role('admin')
    )
    db.session.add(node)
    db.session.commit()
    return jsonify({'data': [node.to_dict()]})

@bp_api_user.route('/<node_id>', methods=['DELETE'])
@login_required
def user_delete_pv_stat_node(node_id):
    ''' Deletes a node from a PV Stats view '''
    node = PVStatsPermissions.query. \
        filter_by(node_id=node_id, user_id=current_user.id). \
        first()
    if not node:
        abort(Response(f'No node {node_id} was found', status=404))
    db.session.delete(node)
    db.session.commit()
    return jsonify({})

@bp_api_user.route('')
@login_required
def user_get_pv_stats():
    ''' Returns all or selected PV stats in JSON '''
    def combine(node, node_pv):
        '''Update PV stats from network_manager result and return'''
        if len(node_pv) > 0:
            node.update(node_pv[0])
        return node

    nodes_query = PVStatsPermissions.query.filter_by(user_id=current_user.id)
    if request.values.get('draw') is None: 
        nodes = [node.to_dict() for node in nodes_query]
    else: # DataTables is serverSide based
        nodes = _filter_nodes(nodes_query, request.values).json

    root_id = Setting.query.get('network.root_id').value
    response = requests.get(
        current_app.config['NETWORK_MANAGER_URL'] + '/api/v1/node',
        data=json.dumps({
            'root_id': root_id,
            'filter': {
                'id': [node['node_id'] for node in nodes if node['allowed']]
            }
        }),
        headers={'Content-type': 'application/json'})
    pv_data = json.loads(response.content.decode('utf-8'))
    pv_data['data'] = [{'node_name': entry['name'], **entry} for entry in pv_data['data']]

    combined_data = [
        combine(node,
            [node_pv for node_pv in pv_data['data'] if node_pv['id'] == node['node_id']])
        for node in nodes]
    if request.values.get('draw') is None:
        return jsonify({'data': combined_data})
    return jsonify({
        'draw': int(request.values['draw']),
        'recordsTotal': nodes['recordsTotal'],
        'recordsFiltered': nodes['recordsFiltered'],
        'data': combined_data
    })

@bp_api_admin.route('/permission')
@roles_required('admin')
def admin_get_nodes_permissions():
    nodes = PVStatsPermissions.query
    if request.values.get('draw') is not None:
        # DataTables requires server side processing
        return _filter_nodes(nodes, request.values)
    return jsonify({'data': [node.to_dict() for node in nodes]})

@bp_api_admin.route('/permission/<id>', methods=['POST'])
@roles_required('admin')
def admin_save_node_permission(id):
    node = PVStatsPermissions.query.get(id)
    if node is None:
        abort(404)
    payload = request.get_json()
    node.allowed = payload.get('allow')
    db.session.commit()
    return jsonify({'data': [node.to_dict()]})
