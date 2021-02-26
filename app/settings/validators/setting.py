'''Validator for setting input'''
from flask_inputs import Inputs
from wtforms import ValidationError

def _is_valid_key(_form, _field):
    pass

def _is_valid_value(_form, _field):
    pass

class SettingValidator(Inputs):
    '''Validator for payment input'''
    json = {
        'key': [_is_valid_key],
        'value': [_is_valid_value]
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
