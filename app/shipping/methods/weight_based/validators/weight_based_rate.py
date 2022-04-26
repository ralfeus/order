from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import Optional

from app.models import Country

def _is_destination_valid(_form, field):
    if Country.query.get(field.data) is None:
        raise ValidationError('destination: Must be existing country code')

def _is_positive_int(_form, field):
    try:
        data = int(field.data)
        if data < 0:
            raise Exception()
    except:
        raise ValidationError(f"{field.id}: Must be positive integer")

class WeightBasedRateValidator(Inputs):
    '''Validator for weight based rate input'''
    json = {
        'destination': [Optional(), _is_destination_valid],
        'minimum_weight': [Optional(), _is_positive_int],
        'maximum_weight': [Optional(), _is_positive_int],
        'weight_step': [Optional(), _is_positive_int],
        'cost_per_kg': [Optional(), _is_positive_int]
    }
    
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
