from flask import Blueprint

bp_api_admin = Blueprint('shipping_fedex_api_admin', __name__,
                        url_prefix='/api/v1/admin/shipping/fedex')
bp_client_admin = Blueprint('shipping_fedex_client_admin', __name__,
                            url_prefix='/admin/shipping/fedex',
                            static_folder='static',
                            template_folder='templates')

def register_blueprints(flask_app):
    from . import routes
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_client_admin)
