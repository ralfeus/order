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

app = Flask(__name__)

Bootstrap(app)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db, compare_type=True)
login = LoginManager(app)
login.login_view = "user_login"
login.logout_view = "user_logout"

# from app.models import *
from app.routes import admin, api, api_admin, client
