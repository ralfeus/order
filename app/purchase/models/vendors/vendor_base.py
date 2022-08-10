from abc import ABCMeta, abstractmethod
from datetime import datetime
import logging
from time import sleep

from exceptions import PurchaseOrderError
from app.orders.models import Subcustomer
from app.purchase.models import PurchaseOrder

ATTEMPTS_TOTAL = 3

class PurchaseOrderVendorBase(metaclass=ABCMeta):
    _logger: logging.Logger = None

    @classmethod
    def __subclasshook__(cls, subclass):
        return subclass is not cls and cls in subclass.__mro__

    @abstractmethod
    def __init__(self, **kwargs):
        pass

    def __repr__(self):
        return f"Object {self.id}"

    @abstractmethod
    def post_purchase_order(self, purchase_order: PurchaseOrder) -> PurchaseOrder:
        pass

    @abstractmethod
    def update_purchase_orders_status(self, customer: Subcustomer, customer_pos: list):
        pass

    def _set_order_products_status(self, ordered_products, status):
        for op in ordered_products:
            op.status = status
            op.when_changed = datetime.now()

    def _try_action(self, action):
        last_exception = None
        for _attempt in range(ATTEMPTS_TOTAL):
            self._logger.debug("Running action %s. Attempt %s of %s", action, _attempt + 1, ATTEMPTS_TOTAL)
            try:
                return action()
            except PurchaseOrderError as ex:
                self._logger.debug("During action %s an error has occurred: %s", action, ex)
                if not last_exception:
                    last_exception = ex
                if ex.final:
                    break
                else:
                    sleep(1)
        if last_exception:
            raise last_exception

    def to_dict(self):
        return {self.id: str(self)}

    @property
    def id(self):
        return type(self).__name__
