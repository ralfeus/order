'''
Initialization of the application
'''

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.config import Config
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
    app = Flask(__name__)
    app.config.from_object(Config)

    Bootstrap(app)
    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login.init_app(app)
    # login.login_view = "user_login"
    # login.logout_view = "user_logout"

    app.register_blueprint(api)
    app.register_blueprint(admin_api)
    app.register_blueprint(admin)
    app.register_blueprint(client)

    return app
