from datetime import datetime

from flask import send_file
from flask import redirect, render_template, flash, current_app, url_for, send_from_directory
from flask_security import roles_required, login_user, logout_user, current_user

from app import db, security
from app.network.models.node import Node
from app.users import bp_client_admin, bp_client_user
from app.users.forms import SignupForm
from app.users.models.user import User

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"users/static/{file}")

@bp_client_user.route('/signup', methods=['GET', 'POST'])
def user_signup():
    """
    User sign-up page.
    GET requests serve sign-up page.
    POST requests validate form & user creation.
    """
    return render_template('signup.html')

@bp_client_admin.route('/', methods=['GET', 'POST'])
@roles_required('admin')
def users():
    '''
    Edits the user settings
    '''
    return render_template('admin_users.html')
