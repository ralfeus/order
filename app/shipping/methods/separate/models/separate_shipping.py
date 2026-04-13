'''SeparateShipping method - shipping cost is charged separately via eurocargo_management'''
from __future__ import annotations

from app import db
from app.models.country import Country
from app.shipping.models.shipping import Shipping
from app.shipping.models.shipping_rate import ShippingRate


class SeparateShipping(Shipping):
    '''Shipping method where cost is charged separately via eurocargo_management.

    At order creation the shipping cost is 0 (the customer pays later on the
    ECmgmt payment page after selecting a carrier).  Country availability is
    controlled by ShippingRate entries for this shipping method: any row whose
    ``destination`` matches the order country means "this country is available",
    regardless of the weight / rate values stored.
    '''

    __mapper_args__ = {'polymorphic_identity': 'separate'}  # type: ignore

    type = 'SeparateShipping'

    def get_edit_url(self) -> str:
        return f'/admin/shipping/separate/{self.id}'

    def get_shipping_cost(self, destination: str, weight: int) -> int:
        '''Returns 0 at order creation time.  Real cost is determined later in ECmgmt.'''
        return 0

    def can_ship(self, country: Country, weight: int, products: list = []) -> bool:
        '''Returns True only when *country* is in the configured available-country list.

        The list is stored as ShippingRate rows for this shipping method.
        Weight and rate values in those rows are ignored; only the destination
        country code is checked.
        '''
        if not self._are_all_products_shippable(products):
            return False
        if not country:
            return True
        country_id = country.id if isinstance(country, Country) else str(country)
        return db.session.query(ShippingRate).filter_by(
            shipping_method_id=self.id,
            destination=country_id,
        ).count() > 0
