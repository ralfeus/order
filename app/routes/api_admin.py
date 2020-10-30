'''
Contains api endpoint routes of the application
'''
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request
from flask_security import roles_required

from app import db
from app.models import User

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')

@admin_api.route('/user/<user_id>', methods=['DELETE'])
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
        
@admin_api.route('/user/<int:user_id>', methods=['POST'])
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
