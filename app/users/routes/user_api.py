from datetime import datetime
from typing import Any
from flask.globals import current_app
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import Response, abort, jsonify, request, redirect
from flask_security import roles_required, login_user

from app import db, security
from app.network.models.node import Node
from app.tools import modify_object
from app.users import bp_api_admin, bp_api_user
from app.users.models.user import Role, User
from app.users.validators.user import UserValidator, UserEditValidator

@bp_api_user.route('/signup', methods=['POST'])
def signup():
    """
    User sign-up page.
    POST requests validate form & user creation.
    """
    logger = current_app.logger.getChild('signup')
    with UserValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't create a user",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            }), 400
    payload: dict[str, Any] = request.get_json() # type: ignore
    existing_user = User.query. \
        filter_by(username=payload['username']).first()
    if existing_user is not None:
        logger.warning("Attempt to create user %s whilst %s exist", existing_user.username, existing_user)
        return jsonify({
            'data': [],
            'error': 'A user already exists.'
        }), 409
    user = security.datastore.create_user( #type: ignore
        username=payload['username'],
        password=payload['password'],
        email=payload.get('email'),
        phone=payload['phone'],
        atomy_id=payload['atomy_id'] if 'atomy_id' in payload and payload['atomy_id'] != '' else None,
        when_created=datetime.now(),
        active=False)
    if user.atomy_id and Node.query.get(user.atomy_id.strip()):
        user.enabled = True
    db.session.add(user) # type: ignore
    db.session.commit()  # type: ignore
    if user.enabled:
        login_user(user)  # Log in as newly created user
        return jsonify({
            'data': [user.to_dict()],
            'error': None
        }), 201
    else:
        logger.info("User %s has been created but not activated", user.username)
        return jsonify ({
            'data': [],
            'error': 'You have succesfully signed up. Wait till adminitrator will activate your account'
        }), 201


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
    users = User.query

    if request.values.get('initialValue') is not None:
        user = users.get(request.values.get('value'))
        return jsonify(
            {'id': user.id, 'text': user.username} \
                if user is not None else {})
    if request.values.get('q') is not None:
        users = users.filter(User.username.like(f'%{request.values["q"]}%'))
    if request.values.get('page') is not None:
        page = int(request.values['page'])
        total_results = users.count()
        users = users.offset((page - 1) * 100).limit(page * 100)
        return jsonify({
            'results': [entry.to_dict() for entry in users],
            'pagination': {
                'more': total_results > page * 100
            }
        })

    return jsonify([user.to_dict() for user in users])


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
    if 'roles' in payload.keys():
        user.roles = Role.query.filter(Role.id.in_(payload['roles'])).all()

    modify_object(user, payload, ['username', 'email', 'phone', 'atomy_id', 'enabled'])
    if 'password' in payload.keys() and payload['password'] != '':
        user.set_password(payload['password'])
    user.when_changed = datetime.now()
    db.session.commit()
    return jsonify({'data': [user.to_dict()]})
