'''
Initialization of the application
'''

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.config import Config
import app.tools

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = "client.user_login"
login.logout_view = "client.user_logout"

import app.jobs

from app.routes.admin import admin
from app.routes.api import api
from app.routes.client import client
from app.routes.api_admin import admin_api

def create_app(**kwargs):
    '''
    Application factory
    '''
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)
    flask_app.logger.setLevel(flask_app.config['LOG_LEVEL'])

    Bootstrap(flask_app)
    db.init_app(flask_app)
    migrate.init_app(flask_app, db, compare_type=True)
    login.init_app(flask_app)

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(admin_api)
    flask_app.register_blueprint(admin)
    flask_app.register_blueprint(client)

    cron = BackgroundScheduler()
    cron.add_job(
        func=app.jobs.import_products,
        trigger="interval", seconds=flask_app.config['PRODUCT_IMPORT_PERIOD'])
    cron.start()

    return flask_app
