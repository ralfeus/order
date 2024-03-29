from flask import Blueprint

bp_api_user = Blueprint('addresses_api_user', __name__, url_prefix='/api/v1/address')
bp_api_admin = Blueprint('addresses_api_admin', __name__, url_prefix='/api/v1/admin/address')
bp_client_user = Blueprint('addresses_client_user', __name__, url_prefix='/addresses',
                           template_folder='templates')
bp_client_admin = Blueprint('addresses_client_admin', __name__, url_prefix='/admin/addresses',
                            template_folder='templates')

def register_blueprints(flask_app):
    from . import routes
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
