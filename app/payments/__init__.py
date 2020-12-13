from flask import Blueprint

bp_api_user = Blueprint('payments_api_user', __name__, 
                        url_prefix='/api/v1/payment')
bp_api_admin = Blueprint('payments_api_admin', __name__, 
                         url_prefix='/api/v1/admin/payment')
bp_client_user = Blueprint('payments_client_user', __name__, 
                           url_prefix='/payments',
                           template_folder='templates')
bp_client_admin = Blueprint('payments_client_admin', __name__, 
                            url_prefix='/admin/payments',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
