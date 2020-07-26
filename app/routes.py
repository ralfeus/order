'''
Contains all routes of the application
'''

<<<<<<< HEAD
from flask import send_from_directory
from flask import Blueprint, redirect, render_template, flash, request, session, url_for, Response
from flask_login import login_required, logout_user, current_user, login_user, logout_user
from app.forms import LoginForm, SignupForm
from app.models import User
# from . import login_manager
from app import app, db

@app.route('/')
@login_required

=======
from flask import redirect, render_template, flash, url_for
from flask_login import login_required, current_user, login_user, logout_user

from app.forms import LoginForm, SignupForm
from app.models import User
from app import app, db, login

@login.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.route('/')
@login_required
>>>>>>> master
def index():
    '''
    Entry point to the application.
    Takes no arguments
    '''
    return render_template('index.html')

<<<<<<< HEAD
@app.route('/signup', methods=['GET', 'POST'])
def signup():
=======
@app.route('/new_order')
@login_required
def new_order():
    '''
    New order form
    '''
    return render_template('new_order.html')

@app.route('/signup', methods=['GET', 'POST'])
def user_signup():
>>>>>>> master
    """
    User sign-up page.

    GET requests serve sign-up page.
    POST requests validate form & user creation.
    """
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user is None:
            user = User(
                username=form.username.data,
                email=form.email.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()  # Create new user
            login_user(user)  # Log in as newly created user
            return redirect('/login')
        flash('A user already exists with that email address.')
    return render_template(
<<<<<<< HEAD
        'signup.jinja2',
=======
        'signup.html',
>>>>>>> master
        title='Create an Account.',
        form=form,
        template='signup-page',
        body="Sign up for a user account."
    )

@app.route('/login', methods=['GET', 'POST'])
<<<<<<< HEAD
def login():
=======
def user_login():
    ''' Login user '''
>>>>>>> master
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect('login')
<<<<<<< HEAD
        login_user(user)
        # , remember=form.remember_me.data
        x = redirect(url_for('index'))
        return x
    
    return render_template('login.jinja2', title='Sign In', form=form)

@app.route("/logout")
@login_required
def logout():
    """User log-out logic."""
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    return redirect(url_for('app.login'))
=======
        login_user(user, remember=True)

        return redirect(url_for('index'))
    
    return render_template('login.html', title='Sign In', form=form)

@app.route("/logout")
@login_required
def user_logout():
    """User log-out logic."""
    logout_user()
    return redirect(url_for('login'))
>>>>>>> master
