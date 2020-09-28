'''
Contains admin routes of the application
'''
from flask import Blueprint, redirect, render_template
from flask_security import roles_required

from app import db
from app.forms import SignupForm
from app.models import User

admin = Blueprint('admin', __name__, url_prefix='/admin')

@admin.route('/')
@roles_required('admin')
def order_products():
    '''
    Shows list of ordered products
    '''
    return render_template('order_products.html')

@admin.route('/users/new', methods=['GET', 'POST'])
@roles_required('admin')
def new_user():
    '''
    Creates new user
    '''
    userform = SignupForm()
    if userform.validate_on_submit():
        user = User()
        userform.populate_obj(user)

        db.session.add(user)
        return redirect('/admin/users')
    return render_template('signup.html', title="Create user", form=userform)

@admin.route('/users', methods=['GET', 'POST'])
@roles_required('admin')
def users():
    '''
    Edits the user settings
    '''
    return render_template('users.html')
