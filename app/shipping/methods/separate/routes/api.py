'''Admin API routes for SeparateShipping'''
from flask import jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.models.country import Country
from app.settings.models.setting import Setting
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


_SETTING_FIELDS = ('currency', 'first_leg')


@bp_api_admin.route('/<int:shipping_id>/settings', methods=['GET'])
@login_required
@roles_required('admin')
def get_settings(shipping_id):
    '''Return shipper currency and first-leg rate for this shipping method.'''
    if not db.session.get(SeparateShipping, shipping_id):
        return jsonify({'error': f'Shipping {shipping_id} not found'}), 404
    return jsonify({
        field: Setting.get(f'shipping.separate.{shipping_id}.{field}')
        for field in _SETTING_FIELDS
    })


@bp_api_admin.route('/<int:shipping_id>/settings', methods=['POST'])
@login_required
@roles_required('admin')
def save_settings(shipping_id):
    '''Save shipper currency and/or first-leg rate for this shipping method.

    Expects JSON body with any subset of: ``{"currency": "USD", "first_leg": "1.5"}``
    '''
    if not db.session.get(SeparateShipping, shipping_id):
        return jsonify({'error': f'Shipping {shipping_id} not found'}), 404

    payload = request.get_json() or {}
    result = {}
    for field in _SETTING_FIELDS:
        if field not in payload:
            continue
        key = f'shipping.separate.{shipping_id}.{field}'
        value = str(payload[field]) if payload[field] is not None else None
        setting = db.session.get(Setting, key)
        if setting is None:
            setting = Setting(key=key, value=value)
            db.session.add(setting)
        else:
            setting.value = value
        result[field] = value
    db.session.commit()
    return jsonify(result)
