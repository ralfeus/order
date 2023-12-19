'''
Shipping method model
'''
from __future__ import annotations
from functools import reduce
import logging
from tempfile import _TemporaryFileWrapper
from typing import Any, Optional
from flask import current_app

from sqlalchemy import Boolean, Column, Integer, String, Text, or_ #type: ignore
from sqlalchemy.orm import relationship #type: ignore
from sqlalchemy.sql.schema import ForeignKey #type: ignore

from app import db
from app.models import Country
from app.models.base import BaseModel
import app.orders.models as o
from exceptions import NoShippingRateError

from .consign_result import ConsignResult
from .shipping_rate import ShippingRate

box_weights = {
    30000: 2200,
    20000: 1900,
    15000: 1400,
    10000: 1000,
    5000: 500,
    2000: 250
}

class Shipping(db.Model, BaseModel): #type: ignore
    '''
    Shipping method model
    '''
    __tablename__ = 'shipping'

    name = Column(String(32))
    type = ''
    enabled = Column(Boolean(), server_default="1")
    discriminator = Column(String(50))
    notification = Column(Text)
    rates = relationship('ShippingRate', lazy='dynamic')
    params = relationship('ShippingParam', lazy='dynamic')

    __mapper_args__ = {'polymorphic_on': discriminator}

    def _are_all_products_shippable(self, products: list[str]):
        from app.products.models.product import Product
        product_ids: list[str] = []
        for product_id in products:
            product_ids += [product_id, product_id.zfill(6)]
        if products:
            shippable_products = Product.query.filter(
                Product.id.in_(product_ids),
                or_(
                    Product.available_shipping.any(Shipping.id == self.id),
                    Product.available_shipping == None))
            non_shippable_products = [
                p for p in products if p not in [sp.id for sp in shippable_products]
            ]
            logging.debug(f"These products are not shippable by {self}: {non_shippable_products}")
            return shippable_products.count() == len(products)
        return True

    def can_ship(self, country: Country, weight: int, products: list[str]=[]) -> bool:
        if not self._are_all_products_shippable(products):
            logging.debug("Not all products are shippable to %s by %s", country, self)
            return False
        if not country:
            return True
        try:
            self.get_shipping_cost(country, weight)
            return True
        except NoShippingRateError:
            logging.debug("Couldn't get shipping cost to %s by %s", country, self)
            return False
        
    def consign(self, order: 'o.Order', config:dict[str, Any]={}) -> ConsignResult:
        '''Creates consignment at shipping provider.
        :param Order order: order, for which consignment is to be created
        :param dic[str, Any] config: configuration to be used for shipping provider
        :raises: :class:`NotImplementedError`: In case the consignment functionality
        is not implemented by a shipping provider
        :returns str: consignment ID'''
        raise NotImplementedError()
    
    def get_edit_url(self) -> str:
        '''Returns URL for editing the shipping method'''
        return None
    
    def _get_print_label_url(self) -> str:
        '''Returns URL of printing label for the shipping method.
        URL should accept `order_id` parameter'''
        return None

    def get_customs_label(self, order) -> tuple[_TemporaryFileWrapper, str]:
        return None, None #type: ignore

    def get_shipping_cost(self, destination: str, weight: int) -> int:
        '''
        Returns shipping cost in KRW to provided destination for provided weight

        :param destination: destination (mostly country)
        :param weight: shipment weight in grams
        '''
        weight = int(weight) if weight is not None else 0
        if isinstance(destination, Country):
            destination = destination.id #type: ignore
        rate = self.rates \
            .filter_by(destination=destination) \
            .filter(ShippingRate.weight >= weight) \
            .order_by(ShippingRate.weight) \
            .first()
        if rate:
            return rate.rate
        raise NoShippingRateError()
    
    def is_consignable(self):
        if not (current_app.config.get("SHIPPING_AUTOMATION") and
                current_app.config['SHIPPING_AUTOMATION']['enabled']):
            return False
        try:
            self.consign(None)
            return True
        except NotImplementedError:
            return False

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'enabled': self.enabled,
            'is_consignable': self.is_consignable(),
            'notification': self.notification,
            'params': [param.to_dict() for param in self.params],
            'edit_url': self.get_edit_url(),
            'links': {
                'edit': self.get_edit_url(),
                'print_label': self._get_print_label_url()
            }
        }

    @staticmethod
    def get_box_weight(package_weight):
        return reduce(
            lambda acc, box: box[1] if package_weight < box[0] else acc,
            box_weights.items(), 0
        ) if package_weight > 0 \
        else 0

class NoShipping(Shipping):
    __mapper_args__ = {'polymorphic_identity': 'noshipping'} #type: ignore
    @property
    def name(self):
        return 'No shipping'
    
    def can_ship(self, country: Country, weight: int, products: list[str]=[]) -> bool:
        if not self._are_all_products_shippable(products):
            return False
        return True

    def get_shipping_cost(self, destination, weight):
        return 0

class PostponeShipping(NoShipping):
    __mapper_args__ = {'polymorphic_identity': 'postpone'} #type: ignore

    @property
    def name(self):
        return "Postpone shipping"

class ShippingParam(db.Model, BaseModel): #type: ignore
    '''Additional Shipping parameter'''
    __tablename__ = 'shipping_params'

    shipping_id = Column(Integer, ForeignKey('shipping.id'))
    label = Column(String(128))
    name = Column(String(128))
    type = Column(String(32))

    def to_dict(self):
        return {
            'label': self.label,
            'name': self.name,
            'type': self.type
        }
