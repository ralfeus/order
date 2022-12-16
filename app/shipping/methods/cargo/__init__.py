from flask import Blueprint

bp_api_admin = Blueprint('shipping_cargo_api_admin', __name__,
                        url_prefix='/api/v1/admin/shipping/cargo')
bp_client_admin = Blueprint('shipping_cargo_client_admin', __name__,
                            url_prefix='/admin/shipping/cargo',
                            static_folder='static',
                            template_folder='templates')

# def register_blueprints(flask_app):
#     from . import routes
#     flask_app.register_blueprint(bp_api_admin)
#     flask_app.register_blueprint(bp_client_admin)
