'''
Contains api endpoint routes of the application
'''
from datetime import datetime

from more_itertools import map_reduce
from operator import itemgetter

from flask import Blueprint, Response, abort, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import Country, Shipping, ShippingRate
from app.orders.models import Order, OrderProduct, OrderProductStatusEntry, \
                              Suborder
from app.currencies.models import Currency

api = Blueprint('api', __name__, url_prefix='/api/v1')

@api.route('/country')
@login_required
def get_countries():
    countries = Country.query.join(ShippingRate)
    return jsonify(sorted(
        list(map(lambda c: c.to_dict(), countries)),
        key=itemgetter('sort_order', 'name')
    ))

# @api.route('/currency')
# def get_currency_rate():
#     '''
#     Returns currency rates related to KRW in JSON:
#         {
#             currency code: currency rate to KRW
#         }
#     '''
#     currencies = {c.code: str(c.rate) for c in Currency.query.all()}
#     return jsonify(currencies)

@api.route('/shipping', defaults={'country_id': None, 'weight': None})
@api.route('/shipping/<country_id>', defaults={'weight': None})
@api.route('/shipping/<country_id>/<int:weight>')
@login_required
def get_shipping_methods(country_id, weight):
    '''
    Returns shipping methods available for specific country and weight (if both provided)
    '''
    country_name = ''
    shipping_methods = Shipping.query.join(ShippingRate)
    if country_id:
        country = Country.query.get(country_id)
        if country:
            country_name = country.name
            shipping_methods = shipping_methods.filter(ShippingRate.destination == country_id)
    if weight:
        shipping_methods = shipping_methods.filter(ShippingRate.weight >= weight)
    if shipping_methods.count():
        return jsonify(sorted(
            list(map(lambda s: s.to_dict(), shipping_methods)),
            key=itemgetter('name')))
    abort(Response(
        f"Couldn't find shipping method to send {weight}g parcel to {country_name}",
        status=409))

@api.route('/shipping/rate/<country>/<shipping_method_id>/<weight>')
@api.route('/shipping/rate/<country>/<weight>', defaults={'shipping_method_id': None})
@login_required
def get_shipping_rate(country, shipping_method_id, weight):
    '''
    Returns shipping cost for provided country and weight
    Accepts parameters:
        country - Destination country
        shipping_method_id - ID of the shipping method
        weight - package weight in grams
    Returns JSON
    '''
    # print(country, weight)
    shipping_rate_query = ShippingRate.query. \
        filter_by(destination=country). \
        filter(ShippingRate.weight > weight)
    if shipping_rate_query.count():
        if shipping_method_id:
            rate = shipping_rate_query. \
                filter_by(shipping_method_id=shipping_method_id, ). \
                order_by(ShippingRate.weight). \
                first()
            return jsonify({
                'shipping_cost': rate.rate
            })
        else:
            rates = map_reduce(shipping_rate_query,
                keyfunc=lambda i: i.shipping_method_id,
                valuefunc=lambda i: i.rate,
                reducefunc=min 
            )
            return jsonify(rates)
    else:
        abort(Response(
            f"Couldn't find rate for {weight}g parcel to {country.title()}",
            status=409
        ))