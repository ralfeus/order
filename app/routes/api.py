'''
Contains api endpoint routes of the application
'''
from operator import itemgetter

from flask import Blueprint, jsonify
from flask_login import login_required

from app.models import Country, User

api = Blueprint('api', __name__, url_prefix='/api/v1')

@api.route('/country')
@login_required
def get_countries():
    return jsonify(sorted(
        list(map(lambda c: c.to_dict(), Country.query)),
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


@api.route('/user')
@login_required
def get_user():
    '''
    Returns list of products in JSON:
        {
            'id': product ID,
            'username': user name,
            'email': user's email,
            'creted': user's profile created,
            'changed': last profile change
        }
    '''
    user_query = User.query.all()
    return jsonify(User.get_user(user_query))
