'''Validator for order input'''
from app.orders.models.order import Order
import re
from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import DataRequired

from app.models.country import Country
from app.shipping.models.shipping import Shipping, NoShipping, PostponeShipping
from app.shipping.models.dhl import DHL

def _are_suborders_valid(_form, field):
    if field.data:
        if field.data.get('subcustomer') is None or field.data['subcustomer'] == '':
            raise ValidationError('suborder.subcustomer:Field is required')
        for op in field.data['items']:
            if op.get('item_code') is not None:
                try:
                    int(op['quantity'])
                except (KeyError, ValueError):
                    raise ValidationError(
                        f"suborder.order_product.quantity:<{op['quantity']}> is not an integer")
            else:
                raise ValidationError("suborder.order_product.item_code:Empty product code")

def _is_dhl_compliant(form, field):
    shipping = Shipping.query.get(form.data['shipping'])
    if isinstance(shipping, DHL):
        if not re.match(r'^[a-zA-Z0-9\s\.,-]+$', field.data):
            raise ValidationError(
                f'{field.id}: The value must contain only latin latters and numbers')

def _is_valid_string_field(form, field):
    validators = {
        DHL: _is_dhl_compliant,
        NoShipping: None,
        PostponeShipping: None
    }
    shipping = Shipping.query.get(form.data['shipping'])
    field_length = getattr(Order, field.name).type.length
    if type(shipping) in validators:
        if validators[type(shipping)] is not None:
            validators[type(shipping)](form, field)
    elif not field.data:
        raise ValidationError(f'{field.name}:Field is required')
    elif len(field.data) > field_length:
        raise ValidationError(
            f'{field.name}:Field value must not be longer than {field_length}')

def _is_valid_country(_form, field):
    country = Country.query.get(field.data)
    if not country:
        raise ValidationError('country:Value is invalid')

class OrderValidator(Inputs):
    '''Validator for order input'''
    json = {
        'address': [_is_valid_string_field],
        'country': [_is_valid_country],
        'customer_name': [_is_valid_string_field],
        'phone': [_is_valid_string_field],
        'shipping': [DataRequired("shipping:Field is required")],
        'suborders': [DataRequired("suborders:Field is required"), _are_suborders_valid],
        'zip': [_is_valid_string_field]
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
        'suborders': [_are_suborders_valid]
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
