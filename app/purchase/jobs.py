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
from exceptions import AtomyLoginError, PurchaseOrderError
from app.orders.models.order_product import OrderProductStatus
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
    # def is_purchase_date_valid(purchase_date):
    #     tz = timezone("Asia/Seoul")
    #     today = datetime.now().astimezone(tz)
    #     days_back = 3 if today.weekday() < 2 else 2
    #     days_forth = 2 if today.weekday() == 5 else 1
    #     min_date = (today - timedelta(days=days_back)).date()
    #     max_date = (today + timedelta(days=days_forth)).date()
    #     return purchase_date is None or (
    #         purchase_date >= min_date and purchase_date <= max_date
    #     )
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
        grouped_vendors = map_reduce(
            pending_purchase_orders,
            lambda po: po.vendor
        )        
        for vendor_id, pos in grouped_vendors.items():
            vendor = PurchaseOrderVendorManager.get_vendor(
                vendor_id, logger=logger, config=current_app.config)
            for po in pos:
                # if not is_purchase_date_valid(po.purchase_date):
                #     logger.info("Skip <%s>: purchase date is %s", po.id, po.purchase_date)
                #     continue
                logger.info("Posting a purchase order %s", po.id)
                try:
                    _, failed_products = vendor.post_purchase_order(po)
                    posted_ops_count = len([op for op in po.order_products
                                               if op.status == OrderProductStatus.purchased])
                    if posted_ops_count == len(po.order_products):
                        po.set_status(PurchaseOrderStatus.posted)
                        po.when_changed = po.when_posted = datetime.now()
                    elif posted_ops_count > 0:
                        po.set_status(PurchaseOrderStatus.partially_posted)
                        po.when_changed = po.when_posted = datetime.now()
                        failed_products = failed_products or \
                            {po.product_id: '' for po in po.order_products
                                if po.status != OrderProductStatus.purchased}
                        po.status_details = "Not posted products:\n" + \
                            '\n'.join([f"{id}: {reason}"
                                for id, reason in failed_products.items()])
                    else:
                        raise PurchaseOrderError(po, vendor, 
                            "No products were posted.")
                        po.set_status(PurchaseOrderStatus.failed)
                        po.when_changed = datetime.now()
                        logger.warning("Purchase order %s posting went successfully but no products were ordered", po.id)
                    logger.info("Posted a purchase order %s", po.id)
                except (PurchaseOrderError, AtomyLoginError) as ex:
                    logger.warning("Failed to post the purchase order %s.", po.id)
                    logger.warning(ex)
                    po.set_status(PurchaseOrderStatus.failed)
                    po.status_details = str(ex)
                    po.when_changed = datetime.now()
                db.session.commit() #type: ignore
        logger.info('Done posting purchase orders')
    except Exception as ex:
        for po in pending_purchase_orders:
            po.set_status(PurchaseOrderStatus.failed)
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
                logger.warning("Couldn't log in as %s (%s)", customer.name, customer.username)
            except:
                logger.exception(
                    "Couldn't update POs status for %s", customer.name)
            subcustomer_num += 1
    db.session.commit()
    logger.info("Done update of PO statuses")
