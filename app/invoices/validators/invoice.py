'''Validator for invoice creation input'''
from app.orders.models.order import Order
import re
from flask_login import current_user
from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import DataRequired

from app.currencies.models.currency import Currency

def _are_valid_orders(_form, field):
    orders = Order.query.filter(Order.id.in_(field.raw_data)).all() \
        if current_user.has_role('admin') else \
            Order.query.filter(Order.id.in_(field.raw_data), Order.user == current_user).all()
    if not orders:
        raise ValidationError(f"{field.name}:No orders with provided IDs were found ")

def _is_positive_number(_form, field):
    try:
        number = float(field.data)
        if number <= 0:
            raise ValidationError(f"{field.name}:Value must be a positive number")
    except (ValueError, TypeError):
        raise ValidationError(f"{field.name}:Value must be a positive number")

def _is_valid_currency(_form, field):
    currency = Currency.query.filter_by(code=field.data).first()
    if not currency:
        raise ValidationError(f"{field.name}:Invalid currency code")
    if not currency.enabled:
        raise ValidationError(f"{field.name}:Currency is not enabled")
    if currency.code == 'KRW':
        raise ValidationError(f"{field.name}:Korean Won is not allowed for invoices")

class InvoiceValidator(Inputs):
    '''Validator for invoice creation input'''
    json = {
        'order_ids': [_are_valid_orders],
        'currency': [_is_valid_currency],
        'rate': [_is_positive_number]
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self

