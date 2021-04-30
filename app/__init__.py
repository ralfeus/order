'''
Initialization of the application
'''
import inspect
import logging
import os

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from flask_security import Security
from flask_security.datastore import SQLAlchemyUserDatastore
from flask_sqlalchemy import SQLAlchemy

import app.tools
from app.utils.services import get_celery, init_celery

celery = get_celery(__name__, 
                    job_modules=['app.jobs', 'app.network.jobs', 'app.purchase.jobs'])
db = SQLAlchemy()
migrate = Migrate()
# login = LoginManager()
from app.users.forms import LoginForm
security = Security()

def create_app(config=None):
    '''
    Application factory
    '''
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
    import app.currencies, app.currencies.routes
    import app.addresses, app.addresses.routes
    import app.invoices, app.invoices.routes
    import app.network, app.network.routes
    import app.notifications, app.notifications.routes
    import app.orders, app.orders.routes
    import app.payments, app.payments.routes
    import app.products, app.products.routes
    import app.purchase, app.purchase.routes
    import app.settings, app.settings.routes
    import app.shipping, app.shipping.routes
    import app.users, app.users.routes

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(client)
    app.currencies.register_blueprints(flask_app)
    app.addresses.register_blueprints(flask_app)
    app.invoices.register_blueprints(flask_app)
    app.network.register_blueprints(flask_app)
    app.notifications.register_blueprints(flask_app)
    app.orders.register_blueprints(flask_app)
    app.payments.register_blueprints(flask_app)
    app.products.register_blueprints(flask_app)
    app.purchase.register_blueprints(flask_app)
    app.settings.register_blueprints(flask_app)
    app.shipping.register_blueprints(flask_app)
    app.users.register_blueprints(flask_app)
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

# __frm = inspect.stack()
# __command = __frm[len(__frm) - 1].filename
# if __command.endswith('celery'):
#     create_app()
