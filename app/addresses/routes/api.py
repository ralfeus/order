from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.addresses import bp_api_admin, bp_api_user
from app.models.address import Address

@bp_api_admin.route('/', defaults={'addresses_id': None}, strict_slashes=False)
@bp_api_user.route('', defaults={'addresses_id': None})
@bp_api_admin.route('/<addresses_id>')
@bp_api_user.route('/<addresses_id>')
@login_required
def get_addresses(addresses_id):
    '''
    Returns all or selected addresses in JSON:
    '''
    addresses = Address.query.all() \
        if addresses_id is None \
        else Address.query.filter_by(id=addresses_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), addresses)))

@bp_api_admin.route('/<addresses_id>', methods=['POST'])
@bp_api_admin.route('/', methods=['POST'], defaults={'addresses_id': None}, strict_slashes=False)
@roles_required('admin')
def save_address(addresses_id):
    '''
    Creates or modifies existing address
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))

    if payload.get('zip'):
        try:
            float(payload['zip'])
        except: 
            abort(Response('Not number', status=400))

    addresses = None
    if addresses_id is None:
        addresses = Address()
        addresses.when_created = datetime.now()
        db.session.add(addresses)
    else:
        addresses = Address.query.get(addresses_id)
        if not addresses:
            abort(Response(f'No addresses <{addresses_id}> was found', status=400))

    for key, value in payload.items():

        if getattr(addresses, key) != value:
            setattr(addresses, key, value)
            addresses.when_changed = datetime.now()

    db.session.commit()
    return jsonify(addresses.to_dict())


@bp_api_admin.route('/<addresses_id>', methods=['DELETE'])
@roles_required('admin')
def delete_addresses(addresses_id):
    '''
    Deletes existing addresses item
    '''
    addresses = Address.query.get(addresses_id)
    if not addresses:
        abort(Response(f'No addresses <{addresses_id}> was found', status=404))

    db.session.delete(addresses)
    db.session.commit()
    return jsonify({
        'status': 'success'
    })
    