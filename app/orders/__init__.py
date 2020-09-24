from flask import Blueprint

bp_api_user = Blueprint('orders_api_user', __name__, url_prefix='/api/v1/order')
bp_api_admin = Blueprint('orders_api_admin', __name__, url_prefix='/api/v1/admin/order')
bp_client_user = Blueprint('orders_client_user', __name__, url_prefix='/orders',
                           template_folder='templates')
bp_client_admin = Blueprint('orders_client_admin', __name__, url_prefix='/admin/orders',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
