from flask import Blueprint

bp_api_user = Blueprint('addresses_api_user', __name__, url_prefix='/api/v1/addresses')
bp_api_admin = Blueprint('addresses_api_admin', __name__, url_prefix='/api/v1/admin/addresses')
bp_client_user = Blueprint('addresses_client_user', __name__, url_prefix='/addresses',
                           template_folder='templates')
bp_client_admin = Blueprint('addresses_client_admin', __name__, url_prefix='/admin/addresses',
                            template_folder='templates')
from .models import *
from . import routes

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
