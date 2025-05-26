from flask import send_file
from flask import render_template
from flask_security import login_required, roles_required

from app.users import bp_client_admin, bp_client_user

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
@login_required
@roles_required('admin')
def users():
    '''
    Edits the user settings
    '''
    return render_template('admin_users.html')
