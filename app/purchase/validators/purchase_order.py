'''Validator for purchase order input'''
import re
from flask_inputs import Inputs
from wtforms import ValidationError

def _is_valid_address(_form, field):
    from app.models.address import Address
    _is_valid_reference_field('address_id', field.data, Address)

def _is_valid_company(_form, field):
    from app.purchase.models.company import Company
    _is_valid_reference_field('company_id', field.data, Company)

def _is_valid_order(_form, field):
    from app.orders.models.order import Order
    _is_valid_reference_field('order_id', field.data, Order)

def _is_valid_phone(_form, field):
    if not re.match(r'\d{3}-\d{4}-\d{4}', field.data):
        raise ValidationError('contact_phone:Must be in format 000-0000-0000')

def _is_valid_reference_field(field, reference, model):
    try:
        entity = model.query.get(reference)
        if entity is None:
            raise Exception()
    except:
        raise ValidationError(f'{field}:Must be existing reference')

def _no_empty_field(_form, field):
    if field.data == '':
        raise ValidationError(f'{field.id}: Field is required')

class PurchaseOrderValidator(Inputs):
    '''Validator for order input'''
    json = {
        'address_id': [_no_empty_field, _is_valid_address],
        'company_id': [_no_empty_field, _is_valid_company],
        'contact_phone': [_no_empty_field, _is_valid_phone],
        'order_id': [_no_empty_field, _is_valid_order]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
