from . import Shipping
from app import db

dhl_zones = db.table('dhl_zones',
    db.Column('zone', db.String(6), index=True),
    db.Column('country_id', db.String(2), db.ForeignKey('countries', 'id'))
)
dhl_rates = db.table('dhl_rates', 
    db.Column('zone', db.String(6), primary_key=True),
    db.Column('weight', db.Float(), primary_key=True),
    db.Column('rate', db.Float())
)

class DHL(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'dhl'}

    def get_shipment_cost(self, destination, weight):
        rates 