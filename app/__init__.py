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

from app.config import Config
import app.tools

db = SQLAlchemy()
migrate = Migrate()
# login = LoginManager()
from app.forms import LoginForm
security = Security()
# security.login_view = "client.user_login"
# security.logout_view = "client.user_logout"

# import app.jobs
# cron = BackgroundScheduler(daemon=True)
# cron.add_job(
#     func=app.jobs.import_products,
#     trigger="interval", seconds=Config.PRODUCT_IMPORT_PERIOD)
# cron.start()



import app.jobs

from app.routes.admin import admin
from app.routes.api import api
from app.routes.client import client
from app.routes.api_admin import admin_api

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

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(admin_api)
    flask_app.register_blueprint(admin)
    flask_app.register_blueprint(client)

    flask_app.logger.info('Routes are registered')

    return flask_app
