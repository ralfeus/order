'''Validator for payment input'''
import re

from flask_inputs import Inputs
from wtforms import ValidationError

from app.users.models.user import User

def _is_int(_form, field):
    if field.data is not None:
        val = re.sub(r'[\s]', '', str(field.data))
        if re.match(r'^-?\d+((\.|,)\d{2})?$', val) is None:
            raise ValidationError(f'{field.id}: The value must be number')

def _is_valid_user(_form, field):
    if User.query.get(field.data) is None:
        raise ValidationError(f'{field.id}: Is not a valid user')

class TransactionValidator(Inputs):
    '''Validator for transaction input'''
    json = {
        'customer_id': [_is_valid_user],
        'amount': [_is_int],
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
