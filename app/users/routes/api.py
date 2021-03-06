from datetime import datetime
from flask.globals import current_app
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import Response, abort, jsonify, request, redirect
from flask_security import roles_required

from app import db
from app.tools import modify_object
from app.users import bp_api_admin
from app.users.models.user import User
from app.users.validators.user import UserValidator, UserEditValidator

@bp_api_admin.route('', methods=['POST'])
@roles_required('admin')
def create_user():
    '''Creates new user'''
    with UserValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't create a user",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            }), 400
    payload = request.get_json()
    user = User(
        username=payload['username'],
        email=payload['email'],
        phone=payload['phone'],
        atomy_id=payload['atomy_id'],
        enabled=True
    )
    user.set_password(payload['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'data': [user.to_dict()]})


@bp_api_admin.route('/<user_ids>', methods=['DELETE'])
@roles_required('admin')
def delete_user(user_ids):
    '''Deletes a user by its user_id'''
    logger = current_app.logger.getChild('delete_user')
    result = None
    try:
        User.query.filter(User.id.in_(user_ids.split(','))).delete(synchronize_session='fetch')
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        logger.warning("Can't delete user %s as it's used in some orders", user_ids)
        result = jsonify({
            'error': f"Can't delete user {user_ids} as it's used in some orders"
        })
        result.status_code = 409

    return result

@bp_api_admin.route('')
@roles_required('admin')
def get_user():
    '''Returns list of products in JSON'''
    user_query = User.query
    return jsonify(User.get_user(user_query))


@bp_api_admin.route('/<int:user_id>', methods=['POST'])
@roles_required('admin')
def save_user(user_id):
    with UserEditValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't update a user",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            }), 400
    user = User.query.get(user_id)
    payload = request.get_json()
    modify_object(user, payload, ['username', 'email', 'phone', 'atomy_id', 'enabled'])
    if 'password' in payload.keys() and payload['password'] != '':
        user.set_password(payload['password'])
    user.when_changed = datetime.now()
    db.session.commit()
    return jsonify({'data': [user.to_dict()]})
