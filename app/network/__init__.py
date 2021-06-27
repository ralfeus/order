from flask import Blueprint

# bp_api_user = Blueprint('network_api_user', __name__, url_prefix='/api/v1/order')
bp_api_admin = Blueprint('network_api_admin', __name__, url_prefix='/api/v1/admin/network')
# bp_client_user = Blueprint('network_client_user', __name__, url_prefix='/network',
#                            template_folder='templates')
bp_client_admin = Blueprint('network_client_admin', __name__, url_prefix='/admin/network',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    # flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    # flask_app.register_blueprint(bp_client_user)

from .models import *
from . import routes
