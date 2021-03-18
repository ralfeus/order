from flask import Blueprint

bp_api_user = Blueprint('currencies_api_user', __name__, url_prefix='/api/v1/currency')
bp_api_admin = Blueprint('currencies_api_admin', __name__, url_prefix='/api/v1/admin/currency')
bp_client_user = Blueprint('currencies_client_user', __name__, url_prefix='/currencies',
                           template_folder='templates')
bp_client_admin = Blueprint('currencies_client_admin', __name__, url_prefix='/admin/currencies',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)