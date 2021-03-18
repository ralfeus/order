'''Validator for order input'''
import re
from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import DataRequired

from app.models.country import Country
from app.shipping.models.shipping import Shipping, NoShipping, PostponeShipping
from app.shipping.models.dhl import DHL

def _is_dhl_compliant(form, field):
    shipping = Shipping.query.get(form.data['shipping'])
    if isinstance(shipping, DHL):
        if not re.match(r'^[a-zA-Z0-9\s\.,-]+$', field.data):
            raise ValidationError(
                f'{field.id}: The value must contain only latin latters and numbers')

def _is_valid_address(form, field):
    validators = {
        DHL: _is_dhl_compliant,
        NoShipping: None,
        PostponeShipping: None
    }
    shipping = Shipping.query.get(form.data['shipping'])
    if type(shipping) in validators:
        if validators[type(shipping)] is not None:
            validators[type(shipping)](form, field)
    elif not field.data:
        raise ValidationError('address:Field is required')

def _is_valid_country(_form, field):
    country = Country.query.get(field.data)
    if not country:
        raise ValidationError('country:Value is invalid')

class OrderValidator(Inputs):
    '''Validator for order input'''
    json = {
        'address': [_is_valid_address],
        'country': [_is_valid_country],
        'customer_name': [DataRequired('customer_name:Field is required'), _is_dhl_compliant],
        'phone': [DataRequired("phone:Field is required"), _is_dhl_compliant],
        'shipping': [DataRequired("shipping:Field is required")],
        'suborders': [DataRequired("suborders:Field is required")],
        'zip': [DataRequired('zip:Field is required'), _is_dhl_compliant]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self

def _no_empty_field(_form, field):
    if field.data == '':
        raise ValidationError(f'{field.id}: Field is required')

class OrderEditValidator(Inputs):
    '''Validator for order edit input'''
    json = {
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
