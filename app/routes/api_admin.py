'''
Contains api endpoint routes of the application
'''
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request
from flask_security import roles_required

from app import db
from app.users.models import User

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')
