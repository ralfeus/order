''' Background jobs for Purchase module'''
from datetime import datetime, timedelta
import logging
from more_itertools import map_reduce
from pytz import timezone

from celery.schedules import crontab
from celery.utils.log import get_task_logger
from flask import current_app
from sqlalchemy import not_

from app import celery, db
from app.exceptions import AtomyLoginError
from app.orders.models.order_product import OrderProduct
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from .models.vendor_manager import PurchaseOrderVendorManager

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(7200, update_purchase_orders_status,
        name='Update PO status every 120 minutes')
    sender.add_periodic_task(crontab(hour=16, minute=0), post_purchase_orders,
        name="Run pending POs every day")

@celery.task
def post_purchase_orders(po_id=None):
    logger = get_task_logger(__name__)
    logger.setLevel(current_app.config['LOG_LEVEL'])
    pending_purchase_orders = PurchaseOrder.query
    if po_id:
        pending_purchase_orders = pending_purchase_orders.filter_by(id=po_id)
    pending_purchase_orders = pending_purchase_orders.filter_by(
        status=PurchaseOrderStatus.pending)
    try: 
        # Wrap whole operation in order to
        # mark all pending POs as failed in case of any failure
        logger.info("There are %s purchase orders to post", pending_purchase_orders.count())
        tz = timezone('Asia/Seoul')
        today = datetime.now().astimezone(tz).date()
        grouped_vendors = map_reduce(
            pending_purchase_orders,
            lambda po: po.vendor
        )        
        for vendor_id, pos in grouped_vendors.items():
            vendor = PurchaseOrderVendorManager.get_vendor(
                vendor_id, logger=logger, config=current_app.config)
            for po in pos:
                if po.purchase_date and po.purchase_date > today + timedelta(days=1):
                    logger.info("Skip <%s>: purchase date is %s", po.id, po.purchase_date)
                    continue
                logger.info("Posting a purchase order %s", po.id)
                try:
                    vendor.post_purchase_order(po)
                    posted_ops_count = po.order_products.filter_by(status='Purchased').count()
                    if posted_ops_count == po.order_products.count():
                        po.status = PurchaseOrderStatus.posted
                        po.when_changed = datetime.now()
                    elif posted_ops_count > 0:
                        po.status = PurchaseOrderStatus.partially_posted
                        po.when_changed = datetime.now()
                        failed_order_products = po.order_products.filter(
                            OrderProduct.status != 'Purchased')
                        po.status_details = "Not posted products:\n" + \
                            '\n'.join(map(
                                lambda fop: f"{fop.product_id}: {fop.product.name}",
                                failed_order_products))
                    else:
                        po.status = PurchaseOrderStatus.failed
                        po.when_changed = datetime.now()
                        logger.warning("Purchase order %s posting went successfully but no products were ordered", po.id)
                    logger.info("Posted a purchase order %s", po.id)
                except Exception as ex:
                    logger.warning("Failed to post the purchase order %s.", po.id)
                    logger.warning(ex)
                    po.status = PurchaseOrderStatus.failed
                    po.status_details = str(ex.args)
                    po.when_changed = datetime.now()
                db.session.commit()
        logger.info('Done posting purchase orders')
    except Exception as ex:
        for po in pending_purchase_orders:
            po.status = PurchaseOrderStatus.failed
        db.session.commit()
        raise ex

@celery.task
def update_purchase_orders_status(po_id=None, browser=None):
    logger = get_task_logger(__name__)
    logger.setLevel(current_app.config['LOG_LEVEL'])
    logger.info("Starting update of PO statuses")
    pending_purchase_orders = PurchaseOrder.query
    if po_id:
        logger.info("Update status of PO <%s>", po_id)
        pending_purchase_orders = pending_purchase_orders.filter_by(id=po_id)
    else:
        logger.info('Update status of all POs')
        pending_purchase_orders = pending_purchase_orders.filter(
            PurchaseOrder.when_created > (datetime.now() - timedelta(weeks=1)).date()
        )
        pending_purchase_orders = pending_purchase_orders.filter(
            not_(PurchaseOrder.status.in_((
                PurchaseOrderStatus.cancelled,
                PurchaseOrderStatus.failed,
                PurchaseOrderStatus.payment_past_due,
                PurchaseOrderStatus.shipped,
                PurchaseOrderStatus.delivered)))
        )
    grouped_vendors = map_reduce(
        pending_purchase_orders,
        lambda po: po.vendor
    )
    vendors_num = len(grouped_vendors)
    vendor_num = 1
    for vendor, customers_pos in grouped_vendors.items():
        logger.info("Updating POs at vendor %s (%d of %d)",
            str(vendor), vendor_num, vendors_num)
        grouped_customers = map_reduce(
            customers_pos,
            lambda po: po.customer)
        subcustomers_num = len(grouped_customers)
        logger.info("There are %d subcustomers to update POs for", subcustomers_num)
        subcustomer_num = 1
        vendor = PurchaseOrderVendorManager.get_vendor(
            vendor, logger=logger, browser=browser, config=current_app.config)
        for customer, customer_pos in grouped_customers.items():
            try:
                logger.info("Updating subcustomer %s (%d of %d) - %d POs",
                    customer.name, subcustomer_num, subcustomers_num, len(customer_pos))
                if len(customer_pos) > 0:
                    vendor.update_purchase_orders_status(customer, customer_pos)
            except AtomyLoginError as ex:
                logger.warning("Couldn't log in as %s: %s", customer.name, str(ex))
            except:
                logger.exception(
                    "Couldn't update POs status for %s", customer.name)
            subcustomer_num += 1
    db.session.commit()
    logger.info("Done update of PO statuses")
