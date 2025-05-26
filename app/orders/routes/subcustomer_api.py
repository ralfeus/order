'''API endpoints for sale order subcustomer management'''
import json
import requests

from flask import Response, abort, current_app, jsonify, request
from flask_security import login_required, roles_required

from sqlalchemy import or_

from utils.atomy import atomy_login2
from exceptions import AtomyLoginError, HTTPError, SubcustomerParseError

from app import db
from app.orders import bp_api_admin, bp_api_user
from app.settings.models import Setting
from app.tools import prepare_datatables_query, modify_object

from ..models.subcustomer import Subcustomer
from ..models.suborder import Suborder

from ..utils import parse_subcustomer

@bp_api_admin.route('/subcustomer')
@login_required
@roles_required('admin')
def admin_get_subcustomers():
    subcustomers = Subcustomer.query
    if request.values.get('draw') is not None: # Args were provided by DataTables
        subcustomers, records_total, records_filtered = \
            prepare_datatables_query(subcustomers, request.values)
        outcome = [entry.to_dict() for entry in subcustomers]

        return jsonify({
            'draw': request.values['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': outcome
        })
    if request.values.get('initialValue') is not None:
        sub = Subcustomer.query.get(request.values.get('value'))
        return jsonify(
            {'id': sub.id, 'text': sub.name} \
                if sub is not None else {})
    if request.values.get('q') is not None:
        subcustomers = Subcustomer.get_filter(subcustomers,
                                              filter_value=request.values["q"])
    if request.values.get('page') is not None:
        page = int(request.values['page'])
        total_results = subcustomers.count()
        subcustomers = subcustomers.offset((page - 1) * 100).limit(page * 100)
        return jsonify({
            'results': [entry.to_dict() for entry in subcustomers],
            'pagination': {
                'more': total_results > page * 100
            }
        })
    return jsonify([entry.to_dict() for entry in subcustomers])

@bp_api_admin.route('/subcustomer', methods=['POST'])
@login_required
@roles_required('admin')
def admin_create_subcustomer():
    payload = request.get_json()
    if payload is None:
        abort(Response("No customer data is provided", status=400))
    try:
        if Subcustomer.query.filter_by(username=payload['username']).first():
            abort(Response("Subcustomer with such username already exists", status=409))
        subcustomer = Subcustomer(
            name=payload['name'],
            username=payload['username'],
            password=payload['password']
        )
        db.session.add(subcustomer)
        db.session.commit()
        node = _invoke_node_api("/api/v1/node/" + payload['username'])
        if node is None:
            _invoke_node_api("/api/v1/node/" + payload['username'],
                             method="put", data=payload)
        else:
            _invoke_node_api("/api/v1/node/" + payload['username'],
                             method="patch", data=payload)
        return jsonify(subcustomer.to_dict())
    except KeyError:
        abort(Response("Not all subcustomer data is provided", status=400))
    
@bp_api_admin.route('/subcustomer/<subcustomer_id>', methods=['POST'])
@login_required
@roles_required('admin')
def admin_save_subcustomer(subcustomer_id):
    payload = request.get_json()
    if payload is None:
        abort(Response("No customer data is provided", status=400))
    subcustomer = Subcustomer.query.get(subcustomer_id)
    if subcustomer is None:
        abort(Response(f"No customer <{subcustomer_id}> is found", status=404))

    if payload.get('username') and \
        Subcustomer.query.filter_by(username=payload['username']).count() > 0:
        abort(Response(
            f"Subcustomer with username <{payload['username']}> already exists",
            status=409))
    modify_object(subcustomer, payload, ['name', 'username', 'password', 'in_network'])
    _invoke_node_api("/api/v1/node/" + subcustomer.username,
                     method="patch", data=payload)

    db.session.commit()
    return jsonify(subcustomer.to_dict())

@bp_api_admin.route('/subcustomer/<subcustomer_id>', methods=['DELETE'])
@login_required
@roles_required('admin')
def admin_delete_subcustomer(subcustomer_id):
    subcustomer = Subcustomer.query.get(subcustomer_id)
    if subcustomer is None:
        abort(Response(f"No customer <{subcustomer_id}> is found", status=404))
    owned_suborders = Suborder.query.filter_by(subcustomer=subcustomer)
    if owned_suborders.count() > 0:
        suborder_ids = ','.join([s.id for s in owned_suborders])
        abort(Response(
            f"Can't delete subcustomer that has suborders: {suborder_ids}", status=409))
    db.session.delete(subcustomer)
    db.session.commit()
    return jsonify({'status': 'success'})


@bp_api_user.route('/subcustomer/validate', methods=['POST'])
@login_required
def validate_subcustomer():
    if not Setting.get('order.new.check_subcustomers'):
        return {'result': 'success', 'message': 'No subcustomer check is performed'}, 200
    payload = request.get_json()
    if not payload or not payload.get('subcustomer'):
        abort(Response('No subcustomer data was provided', status=400))
    
    current_app.logger.debug(f"Validating subcustomer {payload}")
    try:
        subcustomer, _is_new = parse_subcustomer(payload['subcustomer'])
        atomy_login2(subcustomer.username, subcustomer.password)
        return jsonify({'result': 'success'})
    except SubcustomerParseError as ex:
        return jsonify({'result': 'failure', 'message': str(ex)})
    except AtomyLoginError as ex:
        current_app.logger.info("Couldn't validate subcustomer %s", payload)
        return jsonify({'result': 'failure', 'message': str(ex)})

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
