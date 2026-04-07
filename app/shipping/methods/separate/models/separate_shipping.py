'''SeparateShipping method - shipping cost is charged separately when order is packed'''
from __future__ import annotations
from typing import Optional

from app.shipping.models.shipping import Shipping


class SeparateShipping(Shipping):
    '''Shipping method where cost is charged separately after the order is packed.

    At order creation the shipping cost is 0. When the order transitions to
    "packed", the actual shipping cost is calculated via the standard rate
    lookup and the customer is prompted to pay via Revolut through eurocargo_management.
    '''

    __mapper_args__ = {'polymorphic_identity': 'separate'}  # type: ignore

    type = 'SeparateShipping'

    def get_edit_url(self) -> str:
        return f'/admin/shipping/separate/{self.id}'

    def get_shipping_cost(self, destination: str, weight: int) -> int:
        '''Returns 0 at order creation time. Actual cost is set when packed.'''
        #TODO: Raise NoShippingRateError if no rate configured for destination/weight
        return 0

    def get_actual_shipping_cost(self, destination: Optional[str], weight: int) -> int:
        '''Returns the actual shipping cost using the standard rate lookup.'''
        return super().get_shipping_cost(destination or '', weight)
