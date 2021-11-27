from datetime import datetime

from flask import send_file
from flask import redirect, render_template, flash, current_app, url_for, send_from_directory
from flask_security import login_required, roles_required, login_user, logout_user, current_user

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
    logger = current_app.logger.getChild('user_signup')
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = User.query. \
            filter_by(username=form.username.data).first()
        if existing_user is None:
            user = security.datastore.create_user(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                phone=form.phone.data,
                atomy_id=form.atomy_id.data,
                when_created=datetime.now(),
                active=False)
            if user.atomy_id and Node.query.get(user.atomy_id.strip()):
                user.enabled = True
            db.session.add(user)
            db.session.commit()  # Create new user
            if user.enabled:
                login_user(user)  # Log in as newly created user
                return redirect('/')
            else:
                flash('You have succesfully signed up. Wait till adminitrator will activate your account', category='info')
                return render_template('security/register_user.html', form=form)
        else:
            logger.warning("Attempt to create user %s whilst %s exist", existing_user.username, existing_user)
            flash('A user already exists.', category='warning')
    else:
        logger.info("Couldn't create a user: %s", form.errors)
    return render_template(
        'security/register_user.html', #'signup-page',
        title='Create an Account.',
        form=form,
        body="Sign up for a user account."
    )

@bp_client_admin.route('/', methods=['GET', 'POST'])
@roles_required('admin')
def users():
    '''
    Edits the user settings
    '''
    return render_template('admin_users.html')
