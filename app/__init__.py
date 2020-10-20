'''
Initialization of the application
'''

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from flask_security import Security
from flask_security.datastore import SQLAlchemyUserDatastore
from flask_sqlalchemy import SQLAlchemy

# from app.config import Config
import app.tools
from app.utils.services import get_celery, init_celery

celery = get_celery(__name__)
db = SQLAlchemy()
migrate = Migrate()
from app.forms import LoginForm
security = Security()

def create_app(config='config.py'):
    '''
    Application factory
    '''
    flask_app = Flask(__name__)
    # flask_app.config.from_object(config)
    # flask_app.config.from_envvar('ORDER_CONFIG')
    flask_app.config.from_pyfile(config)
    flask_app.logger.setLevel(flask_app.config['LOG_LEVEL'])

    Bootstrap(flask_app)
    db.init_app(flask_app)
    migrate.init_app(flask_app, db, compare_type=True)
    init_celery(celery, flask_app)
    
    from app.models.user import User
    from app.models.role import Role
    security.init_app(flask_app, SQLAlchemyUserDatastore(db, User, Role), login_form=LoginForm)

    register_components(flask_app)
    if flask_app.config.get('DEBUG'):
        init_debug(flask_app)
   
    return flask_app

def register_components(flask_app):
    from app.routes.admin import admin
    from app.routes.api import api
    from app.routes.client import client
    from app.routes.api_admin import admin_api
    import app.currencies, app.currencies.routes
    import app.invoices, app.invoices.routes
    import app.orders, app.orders.routes
    import app.payments, app.payments.routes
    import app.products, app.products.routes
    import app.purchase, app.purchase.routes

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(admin_api)
    flask_app.register_blueprint(admin)
    flask_app.register_blueprint(client)
    app.currencies.register_blueprints(flask_app)
    app.invoices.register_blueprints(flask_app)
    app.orders.register_blueprints(flask_app)
    app.payments.register_blueprints(flask_app)
    app.products.register_blueprints(flask_app)
    app.purchase.register_blueprints(flask_app)
    flask_app.logger.info('Blueprints are registered')


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
