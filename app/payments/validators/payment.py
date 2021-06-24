'''Validator for payment input'''
import re

from flask_inputs import Inputs
from wtforms import ValidationError

from app.currencies.models.currency import Currency
from app.users.models.user import User
from app.payments.models.payment_method import PaymentMethod

def _is_int(_form, field):
    if field.data is not None \
       and not isinstance(field.data, int):
        try:
           val = int(re.sub(r'[\s]', '', field.data))
           if val is None:
            raise Exception()
        except:
            raise ValidationError(f'{field.id}: The value must be integer')


def _is_valid_currency(_form, field):
    if Currency.query.get(field.data) is None:
        raise ValidationError(f'{field.id}: Invalid currency code')

def _is_valid_payment_method(_form, field):
    if field.data is None or PaymentMethod.query.get(field.data['id']) is None:
        raise ValidationError(f'{field.id}.id: Is not a valid payment method')

def _is_valid_user(_form, field):
    if User.query.get(field.data) is None:
        raise ValidationError(f'{field.id}: Is not a valid user')

class PaymentValidator(Inputs):
    '''Validator for payment input'''
    json = {
        'user_id': [_is_valid_user],
        ''
        'amount_received_krw': [_is_int],
        'amount_sent_original': [_is_int],
        'payment_method': [_is_valid_payment_method],
        'currency_code': [_is_valid_currency]
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
