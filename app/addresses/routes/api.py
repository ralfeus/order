from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.tools import modify_object
from app.addresses import bp_api_admin, bp_api_user
from app.models.address import Address

@bp_api_admin.route('', defaults={'address_id': None})
@bp_api_user.route('', defaults={'address_id': None})
@bp_api_admin.route('/<address_id>')
@bp_api_user.route('/<address_id>')
@login_required
def get_addresses(address_id):
    '''
    Returns all or selected address in JSON:
    '''
    addresses = Address.query
    if address_id is not None:
        addresses = addresses.filter_by(id=address_id)

    return jsonify([entry.to_dict() for entry in addresses])

@bp_api_admin.route('/<address_id>', methods=['POST'])
@bp_api_admin.route('', methods=['POST'], defaults={'address_id': None})
@roles_required('admin')
def save_address(address_id):
    '''
    Creates or modifies existing address
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))

    address = None
    if address_id is None:
        address = Address(
            country_id='kr', # we assume all addresses are in Korea
            user_created=True,
            when_created=datetime.now())
        db.session.add(address)
    else:
        address = Address.query.get(address_id)
        if not address:
            abort(Response(f'No address <{address_id}> was found', status=400))

    if payload.get('zip'):
        try:
            float(payload['zip'])
        except: 
            abort(Response('Not a number', status=400))

    modify_object(address, payload,
        ['name', 'zip', 'address_1', 'address_2', 'address_1_eng', 
         'address_2_eng', 'city_eng', 'delivery_comment']
    )

    db.session.commit()
    return jsonify(address.to_dict())


@bp_api_admin.route('/<address_id>', methods=['DELETE'])
@roles_required('admin')
def delete_address(address_id):
    '''
    Deletes existing address item
    '''
    address = Address.query.get(address_id)
    if not address:
        abort(Response(f'No address <{address_id}> was found', status=404))

    db.session.delete(address)
    db.session.commit()
    return jsonify({
        'status': 'success'
    })
    