'''Validator for user input'''
from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import DataRequired, EqualTo

from app.users.models.user import User

def _is_valid_username(_form, field):
    if User.query.get(field.data) is not None:
        raise ValidationError(f'{field.id}: Already exists')

class UserValidator(Inputs):
    '''Validator for user input'''
    json = {
        'username': [DataRequired('username: Field is required'), _is_valid_username],
        'password': [DataRequired('password: Field is required')],
        'confirm': [DataRequired('confirm: Field is required'),
            EqualTo('password', 'confirm: Must be match password')],
        'phone': [DataRequired('phone: Field is required')]        
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self

def _no_empty_field(_form, field):
    if field.data == '':
        raise ValidationError(f'{field.id}: Field is required')

class UserEditValidator(Inputs):
    '''Validator for user edit input'''
    json = {
        'username': [_no_empty_field, _is_valid_username],
        'password': [],
        'confirm': [EqualTo('password', 'confirm: Must be match password')],
        'phone': [_no_empty_field]        
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
