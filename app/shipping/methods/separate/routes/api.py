'''Admin API routes for SeparateShipping'''
from flask import jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.models.country import Country
from app.shipping.models.shipping_rate import ShippingRate

from .. import bp_api_admin
from ..models.separate_shipping import SeparateShipping


@bp_api_admin.route('/<int:shipping_id>/countries', methods=['GET'])
@login_required
@roles_required('admin')
def get_countries(shipping_id):
    '''Return the list of country codes currently enabled for this shipping method.'''
    shipping = db.session.get(SeparateShipping, shipping_id)
    if not shipping:
        return jsonify({'error': f'Shipping {shipping_id} not found'}), 404

    codes = [
        r.destination
        for r in db.session.query(ShippingRate)
        .filter_by(shipping_method_id=shipping_id)
        .all()
    ]
    return jsonify(codes)


@bp_api_admin.route('/<int:shipping_id>/countries', methods=['POST'])
@login_required
@roles_required('admin')
def save_countries(shipping_id):
    '''Replace the enabled-country list for this shipping method.

    Expects JSON body: ``{"countries": ["DE", "FR", ...]}``
    '''
    shipping = db.session.get(SeparateShipping, shipping_id)
    if not shipping:
        return jsonify({'error': f'Shipping {shipping_id} not found'}), 404

    payload = request.get_json() or {}
    new_codes = set(payload.get('countries') or [])

    # Validate: reject codes that don't exist in the countries table
    valid_ids = {c.id for c in db.session.query(Country).all()}
    unknown = new_codes - valid_ids
    if unknown:
        return jsonify({'error': f'Unknown country codes: {sorted(unknown)}'}), 422

    # Sync: delete removed, add new
    existing = (
        db.session.query(ShippingRate)
        .filter_by(shipping_method_id=shipping_id)
        .all()
    )
    existing_codes = {r.destination for r in existing}

    for rate in existing:
        if rate.destination not in new_codes:
            db.session.delete(rate)

    for code in new_codes - existing_codes:
        db.session.add(ShippingRate(
            shipping_method_id=shipping_id,
            destination=code,
            weight=0,
            rate=0,
        ))

    db.session.commit()
    return jsonify(sorted(new_codes))
