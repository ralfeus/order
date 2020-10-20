'''
Contains client routes of the application
'''
from datetime import datetime
from flask import Blueprint, current_app, redirect, render_template, send_from_directory, flash, url_for
from flask_security import login_required, current_user, login_user, logout_user

from app.forms import LoginForm, SignupForm
from app.models import User
from app import db, security

client = Blueprint('client', __name__, url_prefix='/')

# @login.user_loader
# def load_user(user_id):
#     return User.query.get(user_id)

@client.route('/')
@login_required
def index():
    '''
    Entry point to the application.
    Takes no arguments
    '''
    return redirect('/orders/products')

@client.route('/signup', methods=['GET', 'POST'])
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

@client.route('/login', methods=['GET', 'POST'])
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

@client.route("/logout")
@login_required
def user_logout():
    """User log-out logic."""
    logout_user()
    return redirect(url_for('client.user_login'))

@client.route('/upload/<path:path>')
def send_from_upload(path):
    return send_from_directory('upload', path)

@client.route('/test', defaults={'task_id': None})
@client.route('/test/<task_id>')
def test(task_id):
    from app import celery
    result = None
    if task_id is None:
        from app.jobs import add_together
        result = {'result': add_together.delay(2, 3).id}
    else:
        task = celery.AsyncResult(task_id)
        result = {'state': task.state}
        if task.ready():
            result['result'] = task.result

    from flask import jsonify
    
    return jsonify(result)