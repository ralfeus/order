import re
from app import db

from . import PaymentMethod

class Swift(PaymentMethod):
    __mapper_args__ = {'polymorphic_identity': 'swift'}
    
    def __init__(self):
        self.name = 'SWIFT'
    
    def execute_payment(self):
        pass

    def validate_sender_name(self, name):
        if re.match(r'^[a-zA-Z ]+$', name) is None:
            raise Exception('Must contain only latin letters')
