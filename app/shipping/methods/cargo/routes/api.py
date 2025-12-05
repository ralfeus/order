from flask import jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.tools import modify_object, prepare_datatables_query
from app.shipping.models.shipping_rate import ShippingRate

from ..models import Cargo

from .. import bp_api_admin

@bp_api_admin.route("<shipping_id>/countries")
@login_required
@roles_required('admin')
def admin_get_countries(shipping_id):
    '''Returns list of all countries with selection status'''
    from app.models.country import Country

    shipping = Cargo.query.get(shipping_id)
    if shipping is None:
        return {'status': 'No shipping found'}, 404

    # Get selected countries (those with rates)
    selected_countries = {rate.destination for rate in shipping.rates}

    # Get all countries
    countries = Country.query.order_by(Country.sort_order, Country.name).all()

    # Prepare data with selection status
    data = [{
            'id': country.id,
            'name': country.name,
            'selected': country.id in selected_countries
        } for country in countries]

    return jsonify({
            'draw': None,
            'recordsTotal': len(data),
            'recordsFiltered': len(data),
            'data': data
        })

    return jsonify(data)


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

@bp_api_admin.route('<shipping_id>/rate', methods=['post'], defaults={'destination': None})
@login_required
@roles_required('admin')
def admin_save_rate(shipping_id, destination):
    '''Add a country (create rate with rate=0)'''
    payload = request.get_json()
    if payload is None:
        return {'error': 'No payload'}, 400
    shipping = Cargo.query.get(shipping_id)
    if shipping is None:
        return {'error': f'No shipping {shipping_id} found'}, 404

    if 'destination' not in payload:
        return {'error': 'Destination required'}, 400

    # Check if rate already exists for this destination
    existing = shipping.rates.filter_by(destination=payload['destination']).first()
    if existing:
        return {'error': f'Rate for {payload["destination"]} already exists'}, 400

    from app.shipping.models.shipping_rate import ShippingRate
    rate = ShippingRate(
        shipping_method_id=shipping_id,
        destination=payload['destination'],
        weight=0,
        rate=0
    )
    try:
        db.session.add(rate) #type: ignore
        db.session.commit() #type: ignore
        return {'data': [{'id': rate.id, 'destination': rate.destination, 'weight': rate.weight, 'rate': rate.rate}]}, 200
    except Exception as ex:
        db.session.rollback() #type: ignore
        return {'error': str(ex)}, 500

@bp_api_admin.route('<shipping_id>/rate/<destination>', methods=['delete'])
@login_required
@roles_required('admin')
def admin_delete_rate(shipping_id, destination):
    '''Delete a country (remove the rate)'''
    shipping = Cargo.query.get(shipping_id)
    if shipping is None:
        return {'error': f'No shipping {shipping_id} found'}, 404
    rate = shipping.rates.filter_by(destination=destination).first()
    if rate is None:
        return {'error': f'No rate for destination {destination} found'}, 404
    db.session.delete(rate) #type: ignore
    db.session.commit() #type: ignore
    return {'status': 'success'}, 200

@bp_api_admin.route('<shipping_id>/countries', methods=['post'])
@login_required
@roles_required('admin')
def admin_save_countries(shipping_id):
    '''Save selected countries (bulk update)'''
    payload = request.get_json()
    if payload is None or 'selected_countries' not in payload:
        return {'error': 'Selected countries required'}, 400

    shipping = Cargo.query.get(shipping_id)
    if shipping is None:
        return {'error': f'No shipping {shipping_id} found'}, 404

    selected_countries = set(payload['selected_countries'])
    current_selected = {rate.destination for rate in shipping.rates}

    # Countries to add
    to_add = selected_countries - current_selected
    # Countries to remove
    to_remove = current_selected - selected_countries

    from app.shipping.models.shipping_rate import ShippingRate

    try:
        # Add new rates
        for country_id in to_add:
            rate = ShippingRate(
                shipping_method_id=shipping_id,
                destination=country_id,
                weight=0,
                rate=0
            )
            db.session.add(rate) #type: ignore

        # Remove old rates
        for country_id in to_remove:
            rate = shipping.rates.filter_by(destination=country_id).first()
            if rate:
                db.session.delete(rate) #type: ignore

        db.session.commit() #type: ignore
        return {'status': 'success'}, 200
    except Exception as ex:
        db.session.rollback() #type: ignore
        return {'error': str(ex)}, 500
