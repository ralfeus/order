'''
Contains client routes of the application
'''
import os.path
from datetime import datetime
from flask import request, redirect, render_template, send_from_directory, flash, url_for
from flask_login import login_required, current_user, login_user, logout_user

from app.forms import LoginForm, SignupForm, TransactionForm
from app.models import Currency, Transaction, TransactionStatus, User
from app import app, db, login
from app.tools import write_to_file

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
            if not current_user.is_authenticated:
                login_user(user)  # Log in as newly created user
            else:
                return redirect('/admin/users')
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

@app.route('/upload/<path:path>')
def send_from_upload(path):
    return send_from_directory('upload', path)

@app.route('/wallet')
@login_required
def get_wallet():
    return render_template('wallet.html')

@app.route('/wallet/new', methods=['GET', 'POST'])
@login_required
def create_transaction():
    '''
    Creates new transaction request
    '''
    form = TransactionForm()
    file_name = ''
    if form.validate_on_submit():
        if form.proof.data:
            image_data = request.files[form.proof.name].read()
            file_name = os.path.join(
                app.config['UPLOAD_PATH'],
                str(current_user.id),
                datetime.now().strftime('%Y-%m-%d.%H%M%S.%f')) + \
                ''.join(os.path.splitext(form.proof.data.filename)[1:])
            write_to_file(file_name, image_data)

        currency = Currency.query.get(form.currency_code.data)
        new_transaction = Transaction(
            user=current_user,
            amount_original=form.amount_original.data,
            currency=currency,
            amount_krw=form.amount_original.data / currency.rate,
            proof_image=file_name,
            status=TransactionStatus.pending,
            when_created=datetime.now())

        db.session.add(new_transaction)
        try:
            db.session.commit()
            flash("The transaction is created", category='info')
            return redirect('/wallet')
        except Exception as e:
            flash(f"The transaction couldn't be created. {e}", category="error")
    return render_template('generic_form.html', title="Create transaction", form=form)
