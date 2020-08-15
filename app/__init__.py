'''
Initialization of the application
'''

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_admin import Admin
from app.config import Config

from app.config import Config
import app.jobs
import app.tools

# app = Flask(__name__)

# Bootstrap(app)
# app.config.from_object(Config)
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = "client.user_login"
login.logout_view = "client.user_logout"

# from app.models import *
# from app.routes import admin, api, api_admin, client
from app.routes.admin import admin
from app.routes.api import api
from app.routes.client import client
from app.routes.api_admin import admin_api

def create_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)
    flask_app.logger.setLevel(flask.config['LOG_LEVEL'])

    Bootstrap(flask_app)
    db.init_app(flask_app)
    migrate.init_app(flask_app, db, compare_type=True)
    login.init_app(flask_app)
    # login.login_view = "user_login"
    # login.logout_view = "user_logout"

    flask_app.register_blueprint(api)
    flask_app.register_blueprint(admin_api)
    flask_app.register_blueprint(admin)
    flask_app.register_blueprint(client)

    return flask_app
