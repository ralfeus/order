from flask import Blueprint

bp_api_user = Blueprint('products_api_user', __name__, url_prefix='/api/v1/product')
bp_api_admin = Blueprint('products_api_admin', __name__, url_prefix='/api/v1/admin/product')
bp_client_user = Blueprint('products_client_user', __name__, url_prefix='/products',
                           template_folder='templates')
bp_client_admin = Blueprint('products_client_admin', __name__, url_prefix='/admin/products',
                            template_folder='templates')

def register_blueprints(flask_app):
    from . import routes
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)

