from flask import Blueprint

bp_api_admin = Blueprint('shipping_weight_based_api_admin', __name__,
                        url_prefix='/api/v1/admin/shipping/weight_based')
bp_client_admin = Blueprint('shipping_weight_based_client_admin', __name__,
                            url_prefix='/admin/shipping/weight_based',
                            static_folder='static',
                            template_folder='templates')

def register_blueprints(flask_app):
    from . import routes
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_client_admin)
