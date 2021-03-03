'''
Contains api endpoint routes of the application
'''
from operator import itemgetter

from flask import Blueprint, jsonify
from flask_login import login_required

from app.models import Country

api = Blueprint('api', __name__, url_prefix='/api/v1')

@api.route('/country')
@login_required
def get_countries():
    return jsonify(sorted(
        list(map(lambda c: c.to_dict(), Country.query)),
        key=itemgetter('sort_order', 'name')
    ))
