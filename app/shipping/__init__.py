from flask import Blueprint

bp_api_user = Blueprint('shipping_api_user', __name__, url_prefix='/api/v1/shipping')
bp_api_admin = Blueprint('shipping_api_admin', __name__, url_prefix='/api/v1/admin/shipping')
bp_client_user = Blueprint('shipping_client_user', __name__, url_prefix='/shipping',
                           template_folder='templates')
bp_client_admin = Blueprint('shipping_client_admin', __name__, url_prefix='/admin/shipping',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)

from .models import *
from . import routes
