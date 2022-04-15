from app.tools import modify_object
from app.currencies.models.currency_history_entry import CurrencyHistoryEntry
from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.currencies import bp_api_admin, bp_api_user
from app.currencies.models import Currency

@bp_api_admin.route('', defaults={'currency_id': None})
@bp_api_admin.route('/<currency_id>')
@roles_required('admin')
def get_currencies(currency_id):
    '''
    Returns all or selected currencies in JSON:
    '''
    if current_user.has_role('admin'):
        currencies = Currency.query
    if currency_id is not None:
        currencies = currencies.filter_by(code=currency_id)

    return jsonify({'data': [entry.to_dict() for entry in currencies]})

@bp_api_user.route('', defaults={'currency_id': None})
@bp_api_user.route('/<currency_id>')
@login_required
def user_get_currencies(currency_id):
    '''
    Returns all or selected currencies in JSON:
    '''
    currencies = Currency.query.filter_by(enabled=True)
    if currency_id is not None:
        currencies = currencies.filter_by(code=currency_id)

    return jsonify({'data': [entry.to_dict() for entry in currencies]})

@bp_api_admin.route('/<currency_id>', methods=['POST'])
@bp_api_admin.route('', methods=['POST'], defaults={'currency_id': None})
@roles_required('admin')
def save_currency(currency_id):
    ''' Creates or modifies existing currency '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))

    if payload.get('rate'):
        try:
            float(payload['rate'])
        except: 
            abort(Response('Not number', status=400))

    if currency_id is None:
        currency = Currency()
        currency.when_created = datetime.now()
        db.session.add(currency)
    else:
        currency = Currency.query.get(currency_id)
        if not currency:
            abort(Response(f'No currency <{currency_id}> was found', status=400))
    modify_object(currency, payload, ['code', 'name', 'rate', 'enabled'])
    if 'rate' in payload.keys():
        today_rate = currency.history.filter_by(when_created=datetime.now().date()).first()
        if today_rate is None:
            currency.history.append(CurrencyHistoryEntry(
                code=currency.code,
                rate=float(payload['rate']),
                when_created=datetime.now().date()
            ))
        else:
            today_rate.rate = float(payload['rate'])

    db.session.commit()
    return jsonify({'data': [currency.to_dict()]})

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
