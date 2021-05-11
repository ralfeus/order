from flask import Blueprint

bp_api_user = Blueprint('users_api_user', __name__, url_prefix='/api/v1/user')
bp_api_admin = Blueprint('users_api_admin', __name__, url_prefix='/api/v1/admin/user')
bp_client_user = Blueprint('users_client_user', __name__, url_prefix='/users',
                           template_folder='templates')
bp_client_admin = Blueprint('users_client_admin', __name__, url_prefix='/admin/users',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)

from .models import *
from . import routes
