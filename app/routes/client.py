'''
Contains client routes of the application
'''

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
def index():
    '''
    Entry point to the application.
    Takes no arguments
    '''
    return render_template('index.html')

@app.route('/new_order')
@login_required
def new_order():
    '''
    New order form
    '''
    return render_template('new_order.html')

@app.route('/signup', methods=['GET', 'POST'])
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
        if existing_user is None:
            user = User(
                username=form.username.data,
                email=form.email.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()  # Create new user
            login_user(user)  # Log in as newly created user
            return redirect(url_for('user_login'))
        flash('A user already exists.')
    return render_template(
        'signup.html',
        title='Create an Account.',
        form=form,
        template='signup-page',
        body="Sign up for a user account."
    )

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    ''' Login user '''
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('user_login'))
        login_user(user, remember=True)

        return redirect(url_for('index'))
    
    return render_template('login.html', title='Sign In', form=form)

@app.route("/logout")
@login_required
def user_logout():
    """User log-out logic."""
    logout_user()
    return redirect(url_for('user_login'))

@app.route('/wallet')
@login_required
def get_wallet():
    return render_template('wallet.html')