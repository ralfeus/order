import math

from . import Shipping
from app import db
from app.exceptions import NoShippingRateError
from app.models import Country

dhl_zones = db.Table('dhl_zones',
    db.Column('id', db.Integer(), primary_key=True)
)

dhl_countries = db.Table('dhl_countries',
    db.Column('zone', db.Integer(), db.ForeignKey(dhl_zones.c.id)),
    db.Column('country_id', db.String(2), db.ForeignKey('countries.id'))
)

dhl_rates = db.Table('dhl_rates',
    db.Column('zone', db.Integer(), db.ForeignKey(dhl_zones.c.id)),
    db.Column('weight', db.Float()),
    db.Column('rate', db.Float())
)

class DHL(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'dhl'}
    
    def __init__(self):
        self.name = 'DHL'

    def can_ship(self, country: Country, weight: int, products: list=None) -> bool:
        if not self._are_all_products_shippable(products):
            return False
        if weight and weight > 99999:
            return False
        if country is None:
            return True
        return \
            db.session.execute(dhl_countries
                .select(dhl_countries.c.country_id == country.id))\
                .scalar() is not None

    def get_shipping_cost(self, destination, weight):
        weight = int(weight) / 1000
        rate = db.session.execute(dhl_countries
            .join(dhl_zones)
            .join(dhl_rates)
            .select(dhl_rates.c.rate).with_only_columns([dhl_rates.c.rate])
            .where(dhl_countries.c.country_id == destination)
            .where(dhl_rates.c.weight > weight)
            .order_by(dhl_rates.c.weight)
        ).scalar()
        if rate is None:
            raise NoShippingRateError()
        if weight > 30:
            return rate * math.ceil(weight)

        return rate