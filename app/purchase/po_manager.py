from datetime import datetime
import logging
from typing import Optional

from flask import current_app, jsonify
from flask_security import current_user

from app import db
from app.models.address import Address
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.orders.models.suborder import Suborder
from app.products.models.product import DEFAULT_VENDOR
from app.purchase.models import Company
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from app.purchase.models.vendor_manager import PurchaseOrderVendorBase
from app.purchase.signals import purchase_order_deleting, purchase_order_saving
from app.settings.models.setting import Setting
from common.exceptions import PurchaseOrderError

DEFAULT_VENDOR_SETTING = 'purchase.default_vendor.{}'
DEFAULT_ATOMY_PO_VENDOR = 'AtomyQuick'

class NoPurchaseOrderVendorError(PurchaseOrderError):
    '''No purchase order vendor is chosen or set as default for a product vendor'''
    def __str__(self):
        return self.message

def get_default_vendor_id(product_vendor: str) -> Optional[str]:
    '''Returns ID of the purchase order vendor used by default
    for suborders of the product vendor'''
    vendor_id = Setting.get(DEFAULT_VENDOR_SETTING.format(product_vendor))
    if vendor_id:
        return vendor_id
    return DEFAULT_ATOMY_PO_VENDOR if product_vendor == DEFAULT_VENDOR else None

def _get_vendor_id(suborder: Suborder, vendor: Optional[PurchaseOrderVendorBase],
                   vendors: dict[str, str]) -> str:
    '''Returns ID of the purchase order vendor for the suborder.
    The vendor chosen for the product vendor of the suborder goes first.
    Then the single vendor (applies to Atomy suborders only) and then the default one'''
    if vendors.get(suborder.vendor):
        return vendors[suborder.vendor]
    if vendor is not None and suborder.vendor == DEFAULT_VENDOR:
        return vendor.id
    vendor_id = get_default_vendor_id(suborder.vendor)
    if vendor_id is None:
        raise NoPurchaseOrderVendorError(message=
            f"No purchase order vendor is chosen for products of {suborder.vendor}")
    return vendor_id

def create_purchase_orders(order: Order, company: Company, address: Address,
                          vendor: Optional[PurchaseOrderVendorBase]=None,
                          contact_phone: str='', recreate_po=False,
                          purchase_restricted_products=False,
                          vendors: Optional[dict[str, str]]=None,
                          **kwargs
                         ) -> "list[PurchaseOrder]":
    '''Creates purchase order for each suborder of the order.
    :param vendor: purchase order vendor for Atomy suborders
    :param vendors: purchase order vendor IDs by product vendor'''
    logger = logging.getLogger('app.purchase.po_manager.create_purchase_order()')
    suborder_vendors = {suborder.id: _get_vendor_id(suborder, vendor, vendors or {})
                        for suborder in order.suborders}
    existing_pos = PurchaseOrder.query.filter(
            PurchaseOrder.id.like(order.id.replace('ORD', 'PO') + '-%'))
    if existing_pos.count() > 0:
        if recreate_po:
            for po in existing_pos:
                purchase_order_deleting.send(po, **kwargs)
                db.session.delete(po)
        else:
            raise PurchaseOrderError(message=f"Purchase orders for order {order.id} already exist")
    purchase_orders = []
    for suborder in order.suborders:
        purchase_order = PurchaseOrder(
            suborder=suborder,
            customer=suborder.subcustomer,
            contact_phone=contact_phone,
            payment_phone=company.phone,
            status=PurchaseOrderStatus.pending,
            zip=address.zip,
            address_1=address.address_1,
            address_2=address.address_2,
            address=address,
            company=company,
            vendor=suborder_vendors[suborder.id],
            purchase_restricted_products=purchase_restricted_products,
            when_created=datetime.now()
        )
        purchase_order_saving.send(purchase_order, **kwargs)
        db.session.add(purchase_order)
        purchase_orders.append(purchase_order)
        db.session.flush()
    logger.info('Creating purchase order by %s with data: %s',
                current_user, locals())
    order.set_status(OrderStatus.po_created, current_app)
    db.session.commit()
    return purchase_orders
