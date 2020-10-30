from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request, current_user
from flask import redirect, render_template, flash, current_app, url_for, send_from_directory
from flask_security import login_required, roles_required, login_user, logout_user

from app import db, security
from app.users import bp_client_admin, bp_client_user
from app.users.forms import SignupForm, LoginForm
from app.users.models import User

@bp_client_user.route('/signup', methods=['GET', 'POST'])
def user_signup():
    """
    User sign-up page.

    GET requests serve sign-up page.
    POST requests validate form & user creation.
    """
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = db.session.query(User.id). \
            filter_by(username=form.username.data).scalar()
        print(existing_user)
        if existing_user is None:
            user = security.datastore.create_user(
                username=form.username.data, 
                password=form.password.data, 
                email=form.email.data,
                when_created = datetime.now(),
                active=False)
            # user = User(
            #     username=form.username.data,
            #     email=form.email.data
            # )
            # user.set_password(form.password.data)
            # user.when_created = datetime.now()
            db.session.add(user)
            db.session.commit()  # Create new user
            if not current_user.is_authenticated:
                #login_user(user)  # Log in as newly created user
                flash('You have succeswfully signed up. Wait till adminitrator will activate your account', category='info')
            else:
                return redirect('/admin/users')
        else:
            print(existing_user)
            flash('A user already exists.', category='warning')
    return render_template(
        'signup.html',
        title='Create an Account.',
        form=form,
        template='security/register_user.html', #'signup-page',
        body="Sign up for a user account."
    )

@bp_client_user.route('/login', methods=['GET', 'POST'])
def user_login():
    ''' Login user '''
    if current_user.is_authenticated:
        return redirect(url_for('client.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            current_app.logger.warning(f"Failed attempt to log in as <{form.username.data}>")
            flash('Invalid username or password')
            return redirect(url_for('client.user_login'))
        login_user(user, remember=True)
        current_app.logger.info(f"User {user} is logged in")

        return redirect(url_for('client.index'))
    
    return render_template('login.html', title='Sign In', form=form)

@bp_client_user.route("/logout")
@login_required
def user_logout():
    """User log-out logic."""
    logout_user()
    return redirect(url_for('client.user_login'))

@bp_client_user.route('/upload/<path:path>')
def send_from_upload(path):
    return send_from_directory('upload', path)

@bp_client_user.route('/users', methods=['GET', 'POST'])
@roles_required('admin')
def users():
    '''
    Edits the user settings
    '''
    return render_template('users.html')