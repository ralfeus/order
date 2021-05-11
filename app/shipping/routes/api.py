from flask_security.decorators import roles_required
from operator import itemgetter

from flask import Response, abort, jsonify, request
from flask_security import login_required

from app.shipping import bp_api_admin, bp_api_user
from app.exceptions import NoShippingRateError

from app.models import Country
from app.shipping import Box, Shipping

@bp_api_admin.route('')
@roles_required('admin')
def admin_get_shipping_methods():
    return jsonify([shipping.to_dict() for shipping in Shipping.query])

@bp_api_user.route('', defaults={'country_id': None, 'weight': None})
@bp_api_user.route('/<country_id>', defaults={'weight': None})
@bp_api_user.route('/<country_id>/<int:weight>')
@login_required
def get_shipping_methods(country_id, weight):
    '''Returns shipping methods available for specific country and weight (if both provided)'''
    country_name = ''
    country = None
    if country_id:
        country = Country.query.get(country_id)
        if country:
            country_name = country.name

    shipping_methods = Shipping.query.filter_by(enabled=True)
    result = []
    product_ids = []
    product_ids = request.values.get('products').split(',') \
        if request.values.get('products') else []
    for shipping in shipping_methods:
        if shipping.can_ship(country=country, weight=weight, products=product_ids):
            result.append(shipping.to_dict())

    if len(result) > 0:
        return jsonify(sorted(result, key=itemgetter('name')))
    abort(Response(
        f"Couldn't find shipping method to send {weight}g parcel to {country_name}",
        status=409))

@bp_api_user.route('/rate/<country>/<shipping_method_id>/<weight>')
@bp_api_user.route('/rate/<country>/<weight>', defaults={'shipping_method_id': None})
@login_required
def get_shipping_rate(country, shipping_method_id: int, weight):
    '''
    Returns shipping cost for provided country and weight
    Accepts parameters:
        country - Destination country
        shipping_method_id - ID of the shipping method
        weight - package weight in grams
    Returns JSON
    '''
    # print(country, weight)
    shipping_methods = Shipping.query
    if shipping_method_id:
        shipping_method_id = int(shipping_method_id)
        shipping_methods = shipping_methods.filter_by(id=shipping_method_id)
    
    rates = {}
    for shipping_method in shipping_methods:
        try:
            rates[shipping_method.id] = shipping_method.get_shipping_cost(country, weight)
        except NoShippingRateError:
            pass
    if len(rates) > 0:
        if shipping_method_id:
            return jsonify({
                'shipping_cost': rates[shipping_method_id]
            })
        else:
            return jsonify(rates)
    else:
        abort(Response(
            f"Couldn't find rate for {weight}g parcel to {country.title()}",
            status=409
        ))

@bp_api_admin.route('/box')
@roles_required('admin')
def admin_get_shipping_boxes():
    return jsonify([box.to_dict() for box in Box.query])
