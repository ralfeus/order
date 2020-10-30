from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request, redirect, render_template
from flask_security import login_required, roles_required

from app import db
from app.users import bp_api_admin, bp_api_user
from app.users.forms import SignupForm, LoginForm
from app.users.models import User
from app.orders.models import OrderProduct, OrderProductStatusEntry, Suborder

@bp_api_admin.route('/users/new', methods=['GET', 'POST'])
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


@bp_api_admin.route('/user/<user_id>', methods=['DELETE'])
@roles_required('admin')
def delete_user(user_id):
    '''
    Deletes a user by its user_id
    '''
    result = None
    try:
        User.query.filter_by(id=user_id).delete(synchronize_session='fetch')
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete user {user_id} as it's used in some orders"
        })
        result.status_code = 409

    return result

@bp_api_user.route('/user')
@login_required
def get_user():
    '''
    Returns list of products in JSON:
        {
            'id': product ID,
            'username': user name,
            'email': user's email,
            'creted': user's profile created,
            'changed': last profile change
        }
    '''
    user_query = User.query.all()
    return jsonify(User.get_user(user_query))


@bp_api_admin.route('/user/<int:user_id>', methods=['POST'])
@roles_required('admin')
def save_user(user_id):    
    user_input = request.get_json()
    if not user_input:
        abort(Response(f"Can't update user <{user_id}> - no data provided",
                       status=400))
    user = User.query.get(user_id)
    if not user:
        user = User()

    if user_input.get('username') is not None:
        user.username = user_input['username']
    
    if user_input.get('email') is not None:
        user.email = user_input['email']

    if user_input.get('password') is not None:
        user.password = user_input['password']

    if user_input.get('enabled') is not None:
        user.enabled = user_input['enabled']

    if not user.id:
        db.session.add(user)

    user.when_changed = datetime.now()

    db.session.commit()
    return jsonify(user.to_dict())