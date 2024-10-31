from flask import Blueprint

bp_client_admin = Blueprint('shipping_fedex_client_admin', __name__,
                            url_prefix='/admin/shipping/fedex',
                            static_folder='static',
                            template_folder='templates')

def register_blueprints(flask_app):
    from . import routes
    flask_app.register_blueprint(bp_client_admin)
