from importlib import import_module
import logging
import os, os.path
from flask import Blueprint

bp_api_user = Blueprint('shipping_api_user', __name__, url_prefix='/api/v1/shipping')
bp_api_admin = Blueprint('shipping_api_admin', __name__, url_prefix='/api/v1/admin/shipping')
bp_client_user = Blueprint('shipping_client_user', __name__, url_prefix='/shipping',
                           template_folder='templates')
bp_client_admin = Blueprint('shipping_client_admin', __name__, url_prefix='/admin/shipping',
                            template_folder='templates')

def register_blueprints(flask_app):
    logger = logging.getLogger('app.shipping.register_blueprints()')
    from . import routes
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)

    shipping_methods_dir = os.path.dirname(__file__) + '/methods'
    files = os.listdir(shipping_methods_dir)
    for file in files:
        if file.startswith('__'):
            continue
        module_name = os.path.splitext(file)[0]
        try:
            logger.info("Loading shipping: %s", module_name)
            module = import_module(__name__ + '.methods.' + module_name)
            try:
                module.register_blueprints(flask_app)
            except:
                pass
        except KeyError:
            pass


