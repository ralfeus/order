'''Validator for order input'''
import re
from flask_inputs import Inputs
from wtforms.validators import ValidationError

def _is_valid_integer(_form, field):
    try:
        int(field.data)
    except:
        raise ValidationError(f'{field.id}: Must be integer')

def _is_valid_product(_form, field):
    from app.products.models.product import Product
    if Product.query.get(field.data) is None:
        raise ValidationError(f'{field.id}: Must be existing product ID')

class WarehouseProductValidator(Inputs):
    '''Validator for warehouse product input'''
    json = {
        'product_id': [_is_valid_product],
        'quantity': [_is_valid_integer]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
