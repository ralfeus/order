'''Validator for purchase order input'''
import re
from flask_inputs import Inputs
from wtforms import ValidationError

def _is_valid_phone(_form, field):
    if not re.match(r'\d{3}-\d{4}-\d{4}', field.data):
        raise ValidationError('contact_phone:Must be in format 000-0000-0000')

def _no_empty_field(_form, field):
    if field.data == '':
        raise ValidationError(f'{field.id}: Field is required')

class PurchaseOrderValidator(Inputs):
    '''Validator for order input'''
    json = {
        'contact_phone': [_no_empty_field, _is_valid_phone]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
