'''Root PV Stats module'''
from importlib import import_module
import os, os.path
from flask import Blueprint, Flask

# from .signal_handlers import 

bp_api_admin = Blueprint('pv_stats_api_admin', __name__,
                         url_prefix='/api/v1/admin/pv_stats')
bp_client_admin = Blueprint('pv_stats_client_admin', __name__,
                            url_prefix='/admin/pv_stats', template_folder='templates')
bp_api_user = Blueprint('pv_stats_api_user', __name__,
                         url_prefix='/api/v1/pv_stats')
bp_client_user = Blueprint('pv_stats_client_user', __name__,
                            url_prefix='/pv_stats', template_folder='templates')

_current_dir = os.path.dirname(__file__)

def init(app: Flask):
    '''Initializes a PV Stats module'''
    if app.config.get('modules') is None:
        app.config['modules'] = {}
    app.config['modules']['pv_stats'] = True
    _register_signals()
    _import_models()
    _register_routes(app)

def _register_signals():
    pass

def _import_models():
    from . import models

def _register_routes(app: Flask):
    from . import routes
    app.register_blueprint(bp_api_admin)
    app.register_blueprint(bp_client_admin)
    app.register_blueprint(bp_api_user)
    app.register_blueprint(bp_client_user)
