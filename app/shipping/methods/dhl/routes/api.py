'''API routes for DHL module'''
from datetime import datetime
import pandas as pd

from flask_security import roles_required
from sqlalchemy import or_

from app import db

from ..models import DHL
from ..models.dhl_rate import DHLRate
from .. import bp_api_admin

@bp_api_admin.route("rate")
@roles_required('admin')
def admin_get_rates():
    '''Returns list of rates in JSON'''
    rates = DHLRate.query.all()
    df = pd.DataFrame([o.to_dict() for o in rates])
    df['zone'] = df['zone'].map('zone_{}'.format)
    pt = df.pivot_table(values='rate', index=['weight'], columns=['zone'])
    result = [{'weight':i, **pt.loc[i].to_dict()} for i in pt.index]
    return {'data': result}, 200

# @bp_api_admin.route('<shipping_id>/rate/<destination>', methods=['post'])
# @bp_api_admin.route('<shipping_id>/rate', methods=['post'], defaults={'destination': None})
# @roles_required('admin')
# def admin_save_rate(shipping_id, destination):
#     '''Update selected rate'''
#     payload = request.get_json()
#     if payload is None:
#         return {'error': 'No payload'}, 400
#     shipping = WeightBased.query.get(shipping_id)
#     if shipping is None:
#         return {'error': f'No shipping {shipping_id} found'}, 404
#     with WeightBasedRateValidator(request) as validator:
#         if not validator.validate():
#             return jsonify({
#                 'data': [],
#                 'error': "Couldn't update a rate",
#                 'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
#                                 for message in validator.errors]
#             })
#     if destination is None or destination == 'null':
#         rate = WeightBasedRate(shipping_id=shipping_id, when_created=datetime.now())
#         db.session.add(rate)
#     else:
#         destination = destination.split('-')[1]
#         rate = shipping.rates.filter_by(destination=destination).first()
#         if rate is None:
#             return {'error': f'No shipping rate for destination {destination} found'}, 404
#     if payload.get('minimum_weight') is None:
#         payload['minimum_weight'] = rate.minimum_weight
#     if payload.get('maximum_weight') is None:
#         payload['maximum_weight'] = rate.maximum_weight
#     if int(payload['minimum_weight']) > int(payload['maximum_weight']):
#         return {
#             'error': "Couldn't update a rate. Minimum weight must not be more than maximum"
#         }, 400
#     modify_object(rate, payload,
#         ['destination', 'minimum_weight', 'maximum_weight', 'weight_step',
#         'cost_per_kg'])
#     try:
#         db.session.commit()
#         return {'data': [rate.to_dict()]}, 200
#     except Exception as ex:
#         db.session.rollback()
#         return {'error': str(ex)}, 500

# @bp_api_admin.route('<shipping_id>/rate/<destination>', methods=['delete'])
# @roles_required('admin')
# def admin_delete_rate(shipping_id, destination):
#     '''Delete selected rate'''
#     shipping = WeightBased.query.get(shipping_id)
#     if shipping is None:
#         return {'error': f'No shipping {shipping_id} found'}, 404
#     destination = destination.split('-')[1]
#     rate = shipping.rates.filter_by(destination=destination).first()
#     if rate is None:
#         return {'error': f'No shipping rate for destination {destination} found'}, 404
#     db.session.delete(rate)
#     db.session.commit()
#     return {'status': 'success'}, 200
