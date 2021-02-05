from flask_inputs import Inputs
from wtforms import ValidationError

def is_int(form, field):
    if int(field.data) is None:
        raise ValidationError(f'{field.id}: The value must be integer')

class PaymentValidator(Inputs):
    json = {
        'amount_received_krw': [is_int]
    }

    def __enter__(self):
        return self

    def __exit__(self, p1, p2, p3):
        del self
