''' Initialization of the application '''
import logging
import os
import types

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from flask_security import Security
from flask_security.datastore import SQLAlchemyUserDatastore
from flask_sqlalchemy import SQLAlchemy

from app.utils.services import get_celery, init_celery

celery = get_celery(__name__, 
                    job_modules=['app.jobs', 'app.network.jobs', 'app.purchase.jobs'])
db = SQLAlchemy()
migrate = Migrate()
# login = LoginManager()
security = Security()

def create_app(config=None):
    ''' Application factory '''
    from app.users.forms import LoginForm
    flask_app = Flask(__name__)
    # flask_app.config.from_object(config)
    # flask_app.config.from_envvar('ORDER_CONFIG')
    flask_app.config.from_json(config or os.environ.get('OM_CONFIG_FILE') or 'config.json')
    init_logging(flask_app)

    Bootstrap(flask_app)
    db.init_app(flask_app)
    migrate.init_app(flask_app, db, compare_type=True)
    init_celery(celery, flask_app)
    
    from app.users.models.user import User
    from app.users.models.role import Role
    security.init_app(flask_app, SQLAlchemyUserDatastore(db, User, Role), login_form=LoginForm)

    register_components(flask_app)
    if flask_app.config.get('DEBUG'):
        init_debug(flask_app)
   
    return flask_app

def register_components(flask_app):
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
                             and m[1].__name__ != 'app.models'
                             and m[1].__name__.startswith('app.')
                             and m[1].__file__
                             and m[1].__file__.endswith('__init__.py')
                         ]
    for component_module in components_modules:
        component_module.register_blueprints(flask_app)
    flask_app.logger.info('Blueprints are registered')

    load_modules(flask_app)

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

def init_logging(flask_app):
    logger = logging.getLogger()
    logger.setLevel(flask_app.config['LOG_LEVEL'])
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s\t%(levelname)s\t%(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.info("Log level is %s", logging.getLevelName(logger.level))
    flask_app.logger.setLevel(flask_app.config['LOG_LEVEL'])

def load_modules(flask_app):
    from app.modules import init
    init(flask_app)

