''' Initialization of the application '''
from json import JSONEncoder, load
import logging
import os
import re
import time
import types

from blinker import Namespace
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_caching import Cache
from flask_migrate import Migrate
from flask_security import Security
from flask_security.datastore import SQLAlchemyUserDatastore
from flask_sqlalchemy import SQLAlchemy
# from flask_navbar import Nav
# from flask_navbar.elements import Link, Navbar, Subgroup, View

from app.utils.services import get_celery, init_celery

################### JSON serialization patch ######################
# In order to have all objects use to_dict() function providing
# dictionary for JSON serialization
def _default(_self, obj):
    return getattr(obj.__class__, "to_dict", _default.default)(obj) #pyright: ignore

_default.default = JSONEncoder.default  #type: ignore # Save unmodified default.
JSONEncoder.default = _default  #type: ignore # Replace it.
###################################################################


app: Flask
cache = Cache()
db = SQLAlchemy()

celery = get_celery(__name__, 
                    job_modules=['app.jobs', 'app.network.jobs', 'app.purchase.jobs'])
migrate = Migrate()
security = Security()
signals = Namespace()
# nav = Nav()

def create_app(config=None):
    ''' Application factory '''
    global app 
    from app.users.forms.login_form import LoginForm
    config_file = config or os.environ.get('OM_CONFIG_FILE') or 'config-default.json'
    tenant = re.search('[^/]*(?=/config)', config_file).group() \
             if re.search('[^/]*(?=/config)', config_file) \
                else __name__
    app = Flask(__name__)
    app.config.from_file(config_file, load=load)
    app.config['TENANT_NAME'] = tenant
    init_logging(app)

    Bootstrap(app)
    cache.init_app(app)
    init_db(app, db)
    migrate.init_app(app, db, compare_type=True)
    init_celery(celery, app)
    
    from app.users.models.user import User
    from app.users.models.role import Role
    security.init_app(app, SQLAlchemyUserDatastore(db, User, Role), login_form=LoginForm)

    register_components(app)
    # init_navbar(flask_app)
    # if app.config.get('DEBUG'):
    #     init_debug(app)
   
    logging.info("The application is started")
    return app

def register_components(flask_app):
    import_models(flask_app)
    from app.routes.api import api
    from app.routes.client import client
    import app.currencies
    import app.addresses
    import app.orders
    import app.invoices
    import app.network
    import app.notifications
    import app.payments
    import app.products
    import app.purchase
    import app.settings
    import app.shipping
    import app.users

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(client)
    components_modules = [m[1] for m in globals().items()
                          if isinstance(m[1], types.ModuleType)
                             and m[1].__name__ not in ['app.models', 'app.modules', 'app.utils']
                             and m[1].__name__.startswith('app.')
                             and m[1].__file__
                             and m[1].__file__.endswith('__init__.py')
                         ]
    for component_module in components_modules:
        component_module.register_blueprints(flask_app)
    flask_app.logger.info('Blueprints are registered')

    load_modules(flask_app)

def import_models(flask_app):
    import app.currencies.models #pyright: ignore
    import app.addresses.models
    import app.orders.models
    import app.invoices.models
    import app.network.models
    import app.notifications.models
    import app.payments.models
    import app.products.models
    import app.purchase.models
    import app.settings.models
    import app.shipping.methods.cargo.models.cargo
    import app.shipping.methods.dhl.models.dhl
    import app.shipping.methods.ems.models.ems
    import app.shipping.methods.fedex.models.fedex
    import app.shipping.methods.weight_based.models.weight_based
    import app.users.models
    with flask_app.app_context():
        db.create_all()

def init_db(app: Flask, db: SQLAlchemy):
    # from sqlalchemy import text
    logger = logging.getLogger('init_db()')
    db.init_app(app)

    def _dispose_db_pool():
        with app.app_context():
            logging.getLogger('_dispose_db_pool()').info("Disposing DB engine")
            db.engine.dispose() #type: ignore

    try:
        logger.info("Trying to postfork the DB connection")
        from uwsgidecorators import postfork #type: ignore
        postfork(_dispose_db_pool)
    except ImportError:
        logger.info("No UWSGI environment is detected")


def init_debug(flask_app):
    import flask_debugtoolbar
    from flask_debugtoolbar import DebugToolbarExtension
    # from flask_debugtoolbar_lineprofilerpanel.profile import line_profile
    from flask_debug_api import DebugAPIExtension
    DebugToolbarExtension(flask_app)
    flask_app.config['DEBUG_TB_PANELS'] = [
        'flask_debugtoolbar.panels.versions.VersionDebugPanel',
        'flask_debugtoolbar.panels.timer.TimerDebugPanel',
        'flask_debugtoolbar.panels.headers.HeaderDebugPanel',
        'flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel',
        'flask_debugtoolbar.panels.template.TemplateDebugPanel',
        'flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel',
        'flask_debugtoolbar.panels.logger.LoggingPanel',
        'flask_debugtoolbar.panels.profiler.ProfilerDebugPanel'
    ]

    if flask_app.config.get('PROFILER'):
        DebugAPIExtension(flask_app)
            # Add the line profiling
            # 'flask_debugtoolbar_lineprofilerpanel.panels.LineProfilerPanel',
        flask_app.config['DEBUG_TB_PANELS'].append('flask_debug_api.BrowseAPIPanel')

# def init_navbar(app):
#     nav.init_app(app)

def init_logging(flask_app):
    logger = logging.getLogger()
    logger.setLevel(flask_app.config['LOG_LEVEL'])
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s\t%(levelname)s\t%(name)s:%(funcName)s(%(filename)s:%(lineno)d): %(message)s"))
    logger.addHandler(handler)
    logger.info("Starting %s", flask_app.name)
    logger.info("Log level is %s", logging.getLevelName(logger.level))
    flask_app.logger.setLevel(flask_app.config['LOG_LEVEL'])

def load_modules(flask_app):
    from app.modules import init
    init(flask_app)
