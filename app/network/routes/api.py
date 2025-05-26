''' API views for network management'''
import json
import logging
import requests

from flask import abort, current_app, jsonify, request
from flask_security import login_required, roles_required

from app.network import bp_api_admin
from app.tools import convert_datatables_args

@bp_api_admin.route('/builder/<action>')
@login_required
@roles_required('admin')
def get_network_builder_status(action):
    valid_actions = {'start', 'stop', 'status'}
    if action not in valid_actions:
        return jsonify({'status': 'invalid action'})
    try:
        query = '&'.join([f'{k}={v}' for k,v in request.args.items() if v != ''])
        response = requests.get(
            f"{current_app.config['NETWORK_MANAGER_URL']}/api/v1/builder/{action}?{query}",
            headers={'Content-type': 'application/json'})
        data = json.loads(response.content.decode('utf-8'))
    except Exception as e:
        logging.exception(e)
        data = {'status': 'unknown'}
    return jsonify(data)

@bp_api_admin.route('')
@login_required
@roles_required('admin')
def admin_get_nodes():
    '''Returns filtered nodes in JSON'''
    from app.settings.models import Setting
    root_id = Setting.query.get('network.root_id').value
    if request.values.get('draw') is not None: # Args were provided by DataTables
        args = convert_datatables_args(request.values)
        payload = {
            'root_id': root_id,
            'filter': {
                column['data']: column['search']['value']
                for column in args['columns']
                if column['search']['value'] != ''},
            'start': args['start'],
            'limit': args['length']
        }
        try:
            response = requests.get(
                current_app.config['NETWORK_MANAGER_URL'] + "/api/v1/node",
                headers={'Content-type': 'application/json'},
                data=json.dumps(payload))
            data = json.loads(response.content.decode('utf-8'))
        except:
            data = {
                'records_total': 0,
                'records_filtered': 0,
                'data': []
            }
        return jsonify({
            'draw': int(request.values['draw']),
            'recordsTotal': data['records_total'],
            'recordsFiltered': data['records_filtered'],
            'data': data['data']
        })
    abort(400)
