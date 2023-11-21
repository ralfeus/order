'''API routes for warehouse module'''
from calendar import monthrange
from datetime import datetime
import json
import requests

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.settings.models import Setting
from app.tools import prepare_datatables_query
from exceptions import AtomyLoginError, HTTPError
from app.utils.atomy import SessionManager

from .. import bp_api_admin, bp_api_user
from ..models import PVStat


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
    node = PVStat(
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
    node = PVStat.query. \
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
        # if len(node_pv) > 0:
        #     node.update(node_pv[0])
        return {**node, **node_pv[0]} if len(node_pv) > 0 else node

    nodes_query = PVStat.query.filter_by(user_id=current_user.id)
    # Refresh the updating status
    for node in nodes_query.filter_by(is_being_updated=True):
        update_status = _invoke_node_api(f'/api/v1/node/{node.node_id}/update')
        node.is_being_updated = update_status['status'] == 'running'
    db.session.commit()
    if request.values.get('draw') is None:
        nodes = [node.to_dict() for node in nodes_query]
    else: # DataTables is serverSide based
        nodes = _filter_nodes(nodes_query, request.values).json

    root_id = Setting.query.get('network.root_id').value
    pv_data = _invoke_node_api('/api/v1/node', data={
        'root_id': root_id,
        'filter': {
            'id': [node['node_id'] for node in nodes if node['allowed']]
        }
    })  
    pv_data['data'] = [
        {
            'node_name': entry['name'],
            'update_now': entry.get('password') is not None,
            **entry
        } for entry in pv_data['data']
    ]

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

@bp_api_user.route('/<node_id>')
@login_required
def user_get_node_stats(node_id):
    nodes_query = PVStat.query.filter_by(user_id=current_user.id, node_id=node_id)
    if nodes_query.count() == 0:
        abort(403)
    node = _invoke_node_api(f'/api/v1/node/{node_id}')
    if node is None:
        abort(404)
    if node.get('password') is None:
        node_obj = nodes_query.first()
        if node_obj.is_being_updated:
            update_status = _invoke_node_api(f'/api/v1/node/{node_id}/update')
            if update_status['status'] == 'running':
                return {'status': 'update is in progress'}, 202
            node_obj.is_being_updated = False
            db.session.commit()
            node = {
                **node_obj.to_dict(),
                **_invoke_node_api(f'/api/v1/node/{node_id}')
            }
            return node, 200
        _invoke_node_api(f'/api/v1/node/{node_id}/update', method='post')
        node_obj.is_being_updated = True
        db.session.commit()
        return {'status': 'update is in progress'}, 202
            
    try:
        session = SessionManager(username=node_id, password=node['password'])
    except AtomyLoginError:
        abort(Response("Node's password is wrong", status=409))
    node.update(nodes_query.first().to_dict())

    # Build selection range
    today = datetime.today()
    month_range = monthrange(today.year, today.month)
    start_date = today.strftime('%Y-%m-01' if today.day < 16 else '%Y-%m-16')
    end_date = today.strftime(f'%Y-%m-{15 if today.day < 16 else month_range[1]:02d}')
    stats = session.get_json(
        "https://www.atomy.kr/v2/Home/MyAtomy/GetSponsorBenefitOccurList",
        method='POST',
        raw_data=json.dumps({
            "CurrentPageNo": 1,
            "StartDt": start_date,
            "EndDt": end_date,
            "PageSize": 30
    }))
    left_pv = 0
    right_pv = 0
    for item in stats['jsonData']:
        left_pv += item['CurLamt']
        right_pv += item['CurRamt']
    node.update({
        'left_pv': left_pv,
        'right_pv': right_pv,
        'network_pv': node['total_pv'] + left_pv + right_pv,
        'is_being_updated': False,
        'update_now': False
    })

    return jsonify(node)

@bp_api_admin.route('/permission')
@roles_required('admin')
def admin_get_nodes_permissions():
    nodes = PVStat.query
    if request.values.get('draw') is not None:
        # DataTables requires server side processing
        return _filter_nodes(nodes, request.values)
    return jsonify({'data': [node.to_dict() for node in nodes]})

@bp_api_admin.route('/permission/<id>', methods=['POST'])
@roles_required('admin')
def admin_save_node_permission(id):
    node = PVStat.query.get(id)
    if node is None:
        abort(404)
    payload = request.get_json()
    node.allowed = payload.get('allow')
    db.session.commit()
    return jsonify({'data': [node.to_dict()]})

def _invoke_node_api(path, method='get', data={}):
    response = requests.request(
        method=method,
        url=current_app.config['NETWORK_MANAGER_URL'] + path,
        headers={'Content-type': 'application/json'},
        data=json.dumps(data))
    if response.status_code in (200, 201):
        return json.loads(response.content.decode('utf-8'))
    elif response.status_code == 404:
        return None
    else:
        raise HTTPError(status=response.status_code)
