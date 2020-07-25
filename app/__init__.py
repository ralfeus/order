'''
Initialization of the application
'''
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.config import Config

app = Flask(__name__)

Bootstrap(app)
app.config.from_object(Config)
login = LoginManager(app)
login.login_view = "user_login"
login.logout_view = "user_logout"
db = SQLAlchemy(app)
migrate = Migrate(app, db, compare_type=True)

from app import routes, routes_admin, routes_api, models
