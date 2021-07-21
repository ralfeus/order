'''Validator for order input'''
from flask_inputs import Inputs
from wtforms.validators import DataRequired

class WarehouseValidator(Inputs):
    '''Validator for warehouse input'''
    json = {
        'name': [DataRequired("name:Field is required")]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
