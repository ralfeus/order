import re
from app import db

from . import PaymentMethod

class Swift(PaymentMethod):
    __mapper_args__ = {'polymorphic_identity': 'swift'}
    
    def __init__(self):
        self.name = 'SWIFT'
    
    def execute_payment(self):
        pass
