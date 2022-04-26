from flask_inputs import Inputs
from wtforms import ValidationError
from wtforms.validators import Optional, Regexp

from app.models import Country

def _is_destination_valid(field, _form):
    if Country.query.get(field.data) is None:
        raise ValidationError('destination: Must be existing country code')

class WeightBasedRateValidator(Inputs):
    '''Validator for weight based rate input'''
    json = {
        'destination': [Optional(), _is_destination_valid],
        'minimum_weight': [Optional(), Regexp(r'^\d+$', message="minimum_weight: Must be positive integer")],
        'maximum_weight': [Optional(), Regexp(r'^\d+$', message="maximum_weight: Must be positive integer")],
        'weight_step': [Optional(), Regexp(r'^\d+$', message="weight_step: Must be positive integer")],
        'cost_per_kg': [Optional(), Regexp(r'^\d+$', message="cost_per_kg: Must be positive integer")]
    }
    
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        del self
