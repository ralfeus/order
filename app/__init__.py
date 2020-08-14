'''
Initialization of the application
'''

from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin
from app.config import Config

import app.tools

flask = Flask(__name__)
flask.config.from_object(Config)
flask.logger.setLevel(flask.config['LOG_LEVEL'])

Bootstrap(flask)
db = SQLAlchemy(flask)
migrate = Migrate(flask, db, compare_type=True)
login = LoginManager(flask)
login.login_view = "user_login"
login.logout_view = "user_logout"

# from app.models import *
import app.jobs
from app.routes import admin, api, api_admin, client
