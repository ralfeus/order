from datetime import datetime
import logging

from flask import current_app
from flask_security import current_user

from app import db
from app.models.address import Address
from app.orders.models import Order
from app.orders.models.order import OrderStatus
from app.purchase.models import Company
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from app.purchase.models.vendor_manager import PurchaseOrderVendorBase

def create_purchase_orders(order: Order, company: Company, address: Address,
                          vendor: PurchaseOrderVendorBase, contact_phone: str,
                          recreate_po=False, purchase_restricted_products=False
                         ) -> "list[PurchaseOrder]":
    logger = logging.getLogger('app.purchase.po_manager.create_purchase_order()')
    if recreate_po:
        PurchaseOrder.query.filter(
            PurchaseOrder.id.like(order.id.replace('ORD', 'PO') + '-%')) \
            .delete(synchronize_session=False)
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
            vendor=vendor.id,
            purchase_restricted_products=purchase_restricted_products,
            when_created=datetime.now()
        )
        purchase_orders.append(purchase_order)
        db.session.add(purchase_order)
        db.session.flush()
    logger.info('Creating purchase order by %s with data: %s',
                current_user, locals())
    order.set_status(OrderStatus.po_created, current_app)
    db.session.commit()
    return purchase_orders
