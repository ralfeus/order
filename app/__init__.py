'''
Initialization of the application
'''

# from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_bootstrap import Bootstrap
# from flask_login import LoginManager
from flask_migrate import Migrate
from flask_security import Security
from flask_security.datastore import SQLAlchemyUserDatastore
from flask_sqlalchemy import SQLAlchemy

import flask_debugtoolbar
from flask_debugtoolbar import DebugToolbarExtension
from flask_debugtoolbar_lineprofilerpanel.profile import line_profile
from flask_debug_api import DebugAPIExtension
toolbar = DebugToolbarExtension()


from app.config import Config
import app.tools

db = SQLAlchemy()
migrate = Migrate()
from app.forms import LoginForm
security = Security()

def create_app(config=Config, import_name=None):
    '''
    Application factory
    '''
    flask_app = Flask(__name__)
    flask_app.config.from_object(config)
    flask_app.logger.setLevel(flask_app.config['LOG_LEVEL'])
    flask_app.logger.info(config)
    flask_app.logger.info(import_name)

    Bootstrap(flask_app)
    db.init_app(flask_app)
    migrate.init_app(flask_app, db, compare_type=True)
    # login.init_app(flask_app)
    from app.models.user import User
    from app.models.role import Role
    security.init_app(flask_app, SQLAlchemyUserDatastore(db, User, Role), login_form=LoginForm)

    register_components(flask_app)
    flask_app.logger.info('Blueprints are registered')
    # init_data(flask_app)
    if flask_app.config.get('PROFILER'):
        DebugAPIExtension(flask_app)
        flask_app.config['DEBUG_TB_PANELS'] = [
            'flask_debugtoolbar.panels.versions.VersionDebugPanel',
            'flask_debugtoolbar.panels.timer.TimerDebugPanel',
            'flask_debugtoolbar.panels.headers.HeaderDebugPanel',
            'flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel',
            'flask_debugtoolbar.panels.template.TemplateDebugPanel',
            'flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel',
            'flask_debugtoolbar.panels.logger.LoggingPanel',
            'flask_debugtoolbar.panels.profiler.ProfilerDebugPanel',
            # Add the line profiling
            'flask_debugtoolbar_lineprofilerpanel.panels.LineProfilerPanel',
            'flask_debug_api.BrowseAPIPanel'
        ]    
    if flask_app.config.get('DEBUG'):
        toolbar.init_app(flask_app)


    return flask_app

def register_components(flask_app):
    from app.routes.admin import admin
    from app.routes.api import api
    from app.routes.client import client
    from app.routes.api_admin import admin_api
    import app.currencies, app.currencies.routes
    import app.invoices, app.invoices.routes
    import app.orders, app.orders.routes
    import app.products, app.products.routes
    import app.payments, app.payments.routes

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(admin_api)
    flask_app.register_blueprint(admin)
    flask_app.register_blueprint(client)
    app.currencies.register_blueprints(flask_app)
    app.invoices.register_blueprints(flask_app)
    app.orders.register_blueprints(flask_app)
    app.products.register_blueprints(flask_app)
    app.payments.register_blueprints(flask_app)
