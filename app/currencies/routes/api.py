from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.currencies import bp_api_admin, bp_api_user
from app.currencies.models import Currency

@bp_api_admin.route('/', defaults={'currency_id': None}, strict_slashes=False)
@bp_api_user.route('', defaults={'currency_id': None})
@bp_api_admin.route('/<currency_id>')
@bp_api_user.route('/<currency_id>')
@login_required
def get_currencies(currency_id):
    '''
    Returns all or selected currencies in JSON:
    '''
    currencies = Currency.query.all() \
        if currency_id is None \
        else Currency.query.filter_by(id=currency_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), currencies)))

@bp_api_admin.route('/<currency_id>', methods=['POST'])
@bp_api_admin.route('/', methods=['POST'], defaults={'currency_id': None}, strict_slashes=False)
@roles_required('admin')
def save_currency_item(currency_id):
    '''
    Creates or modifies existing currency
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))

    if payload.get('rate'):
        try:
            float(payload['rate'])
        except: 
            abort(Response('Not number', status=400))

    currency = None
    if currency_id is None:
        currency = Currency()
        currency.when_created = datetime.now()
        db.session.add(currency)
    else:
        currency = Currency.query.get(currency_id)
        if not currency:
            abort(Response(f'No currency <{currency_id}> was found', status=400))

    for key, value in payload.items():

        if getattr(currency, key) != value:
            setattr(currency, key, value)
            currency.when_changed = datetime.now()

    db.session.commit()
    return jsonify(currency.to_dict())

@bp_api_admin.route('/<currency_id>', methods=['DELETE'])
@roles_required('admin')
def delete_currency(currency_id):
    '''
    Deletes existing currency item
    '''
    currency = Currency.query.get(currency_id)
    if not currency:
        abort(Response(f'No currency <{currency_id}> was found', status=404))

    db.session.delete(currency)
    db.session.commit()
    return jsonify({
        'status': 'success'
    })
