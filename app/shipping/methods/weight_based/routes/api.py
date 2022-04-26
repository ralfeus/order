from datetime import datetime
from flask import jsonify, request
from flask_security import roles_required
from sqlalchemy import or_

from app import db
from app.tools import modify_object, prepare_datatables_query

from ..models import WeightBased, WeightBasedRate
from ..validators.weight_based_rate import WeightBasedRateValidator
from .. import bp_api_admin

@bp_api_admin.route("<shipping_id>/rate/<rate_id>")
@bp_api_admin.route("<shipping_id>/rate", defaults={'rate_id': None})
@roles_required('admin')
def admin_get_rates(shipping_id, rate_id):
    '''Returns list of rates in JSON'''
    shipping = WeightBased.query.get(shipping_id)
    if shipping is None:
        return {'status': 'No shipping found'}, 404
    rates = shipping.rates
    if rate_id:
        rates = rates.filter_by(id=rate_id)
    if request.values.get('draw') is not None:  # Args were provided by DataTables
        return _filter_rates(rates, request.values)
    if request.values.get('initialValue') is not None:
        sub = rates.get(request.values.get('value')[1:-1])
        return jsonify(
            {'id': sub.id, 'text': sub.name}
            if sub is not None else {})
    if request.values.get('q') is not None:
        rates = rates.filter(or_(
            WeightBased.id.like(f'%{request.values["q"]}%'),
            WeightBased.name.like(f'%{request.values["q"]}%')
        ))
    if request.values.get('page') is not None:
        page = int(request.values['page'])
        total_results = rates.count()
        rates = rates.offset((page - 1) * 100).limit(page * 100)
        return jsonify({
            'results': [entry.to_dict() for entry in rates],
            'pagination': {
                'more': total_results > page * 100
            }
        })

    return jsonify([rate.to_dict() for rate in rates])


def _filter_rates(rates, filter_params):
    rates, records_total, records_filtered = prepare_datatables_query(
        rates, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict(details=True) for entry in rates]
    })

@bp_api_admin.route('<shipping_id>/rate/<destination>', methods=['post'])
@bp_api_admin.route('<shipping_id>/rate', methods=['post'], defaults={'destination': None})
@roles_required('admin')
def admin_save_rate(shipping_id, destination):
    '''Update selected rate'''
    payload = request.get_json()
    if payload is None:
        return {'error': 'No payload'}, 400
    shipping = WeightBased.query.get(shipping_id)
    if shipping is None:
        return {'error': f'No shipping {shipping_id} found'}, 404
    with WeightBasedRateValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't update a rate",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    if destination is None or destination == 'null':
        rate = WeightBasedRate(shipping_id=shipping_id, when_created=datetime.now())
        db.session.add(rate)
    else:
        destination = destination.split('-')[1]
        rate = shipping.rates.filter_by(destination=destination).first()
        if rate is None:
            return {'error': f'No shipping rate for destination {destination} found'}, 404
    if payload.get('minimum_weight') is None:
        payload['minimum_weight'] = rate.minimum_weight
    if payload.get('maximum_weight') is None:
        payload['maximum_weight'] = rate.maximum_weight
    if int(payload['minimum_weight']) > int(payload['maximum_weight']):
        return {
            'error': "Couldn't update a rate. Minimum weight must not be more than maximum"
        }, 400
    modify_object(rate, payload,
        ['destination', 'minimum_weight', 'maximum_weight', 'weight_step',
        'cost_per_kg'])
    try:
        db.session.commit()
        return {'data': [rate.to_dict()]}, 200
    except Exception as ex:
        db.session.rollback()
        return {'error': str(ex)}, 500

@bp_api_admin.route('<shipping_id>/rate/<destination>', methods=['delete'])
@roles_required('admin')
def admin_delete_rate(shipping_id, destination):
    '''Delete selected rate'''
    shipping = WeightBased.query.get(shipping_id)
    if shipping is None:
        return {'error': f'No shipping {shipping_id} found'}, 404
    destination = destination.split('-')[1]
    rate = shipping.rates.filter_by(destination=destination).first()
    if rate is None:
        return {'error': f'No shipping rate for destination {destination} found'}, 404
    db.session.delete(rate)
    db.session.commit()
    return {'status': 'success'}, 200
