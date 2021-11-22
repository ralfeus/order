'''
Shipping method model
'''
from functools import reduce

from sqlalchemy import Boolean, Column, String, Text, or_
from sqlalchemy.orm import relationship

from app import db
from exceptions import NoShippingRateError

from .shipping_rate import ShippingRate
from app.models import Country
from app.models.base import BaseModel

box_weights = {
    30000: 2200,
    20000: 1900,
    15000: 1400,
    10000: 1000,
    5000: 500,
    2000: 250
}

class Shipping(db.Model, BaseModel):
    '''
    Shipping method model
    '''
    __tablename__ = 'shipping'

    name = Column(String(16))
    enabled = Column(Boolean(), server_default="1")
    discriminator = Column(String(50))
    notification = Column(Text)
    rates = relationship('ShippingRate', lazy='dynamic')

    __mapper_args__ = {'polymorphic_on': discriminator}

    def _are_all_products_shippable(self, products):
        from app.products.models.product import Product
        product_ids = []
        for product_id in products:
            product_ids += [product_id, '0' * (6 - len(product_id)) + product_id]

        if products:
            shippable_products = Product.query.filter(
                Product.id.in_(product_ids),
                or_(
                    Product.available_shipping.any(Shipping.id == self.id),
                    Product.available_shipping == None))
            return shippable_products.count() == len(products)
        return True

    def can_ship(self, country: Country, weight: int, products: list=None) -> bool:
        if not self._are_all_products_shippable(products):
            return False
        if not country:
            return True
        rates = self.rates.filter_by(destination=country.id)
        if weight:
            rates = rates.filter(ShippingRate.weight >= weight)
        return rates.count() > 0


    def get_shipping_cost(self, destination, weight):
        '''
        Returns shipping cost to provided destination for provided weight

        :param destination: destination (mostly country)
        :param weight: shipment weight in grams
        '''
        rate = self.rates \
            .filter_by(destination=destination) \
            .filter(ShippingRate.weight >= weight) \
            .order_by(ShippingRate.weight) \
            .first()
        if rate:
            return rate.rate
        raise NoShippingRateError()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'enabled': self.enabled,
            'notification': self.notification
        }

    @staticmethod
    def get_box_weight(package_weight):
        return reduce(
            lambda acc, box: box[1] if package_weight < box[0] else acc,
            box_weights.items(), 0
        ) if package_weight > 0 \
        else 0

class NoShipping(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'noshipping'}
    @property
    def name(self):
        return 'No shipping'
    
    def can_ship(self, country: Country, weight: int, products: list=None) -> bool:
        if not self._are_all_products_shippable(products):
            return False
        return True

    def get_shipping_cost(self, destination, weight):
        return 0

class PostponeShipping(NoShipping):
    __mapper_args__ = {'polymorphic_identity': 'postpone'}

    @property
    def name(self):
        return "Postpone shipping"
