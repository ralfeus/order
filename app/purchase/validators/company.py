'''Validator for company input'''
import re
from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import AnyOf, Optional

def _is_integer(_form, field):
    if not re.match(r'\d+', field.data):
        raise ValidationError(f'{field.id}:Must be integer')

def _is_valid_phone(_form, field):
    if not re.match(r'\d{3}-\d{4}-\d{4}', field.data):
        raise ValidationError(f'{field.id}:Must be in format 000-0000-0000')

def _is_valid_tax_id(_form, field):
    if not re.match(r'\d{3}-\d{2}-\d{5}', field.data):
        raise ValidationError('tax_id:Must be in format 000-00-0000')

def _no_empty_field(_form, field):
    if field.data == '':
        raise ValidationError(f'{field.id}: Field is required')
        
class CompanyValidator(Inputs):
    '''Validator for order input'''
    json = {
        'id': [Optional(), _is_integer],
        'default': [Optional(), AnyOf([True, False], 'default: Must be bool')],
        'phone': [Optional(), _is_valid_phone],
        'tax_id': [_no_empty_field, _is_valid_tax_id],
        'tax_phone': [Optional(), _is_valid_phone]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
