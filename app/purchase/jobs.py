''' Background jobs for Purchase module'''
from datetime import datetime, timedelta
import logging
from time import sleep
from more_itertools import map_reduce
from pytz import timezone

from celery.schedules import crontab
from celery.utils.log import get_task_logger
from flask import current_app
from sqlalchemy import not_, select, text, update

from app import celery, db
from common.exceptions import AtomyLoginError, PurchaseOrderError
from app.orders.models.order_product import OrderProductStatus
from app.orders.models.subcustomer import Subcustomer
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from .models.vendor_manager import PurchaseOrderVendorManager

@celery.on_after_finalize.connect #type: ignore
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(7200, update_purchase_orders_status,
        name='Update PO status every 120 minutes')
    sender.add_periodic_task(crontab(hour=16, minute=0), post_purchase_orders,
        name="Run pending POs every day")

def _get_posting_pos_for_customer(subcustomer_id, worker_id, logger):
    ''' Return all POs currently in "posting" state for a customer.
        Caller must hold the advisory lock for this customer. '''
    posting_pos = db.session.execute( #type: ignore
        select(PurchaseOrder).where(
            PurchaseOrder.customer_id == subcustomer_id,
            PurchaseOrder.status == PurchaseOrderStatus.posting
        )
    ).scalars().all()
    if posting_pos:
        logger.info("[%s] Found %d posting POs for customer id=%s",
                    worker_id, len(posting_pos), subcustomer_id)
    return posting_pos


def _post_claimed_pos(claimed_pos, username, worker_id, logger):
    ''' Post a pre-claimed list of POs to their vendors and update their statuses. '''
    try:
        grouped_vendors = map_reduce(claimed_pos, lambda po: po.vendor)
        for vendor_id, pos in grouped_vendors.items():
            vendor = PurchaseOrderVendorManager.get_vendor(
                vendor_id, logger=logger, config=current_app.config)
            for po in pos:
                logger.info("[%s] Posting a purchase order %s", worker_id, po.id)
                try:
                    sleep(current_app.config.get("PO_POSTING_DELAY_SECONDS", 0))
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
                            {op.product_id: '' for op in po.order_products
                                if op.status != OrderProductStatus.purchased}
                        po.status_details = "Not posted products:\n" + \
                            '\n'.join([f"{id}: {reason}"
                                for id, reason in failed_products.items()])
                    else:
                        raise PurchaseOrderError(po, vendor, "No products were posted.")
                    logger.info("[%s] Posted a purchase order %s", worker_id, po.id)
                except (PurchaseOrderError, AtomyLoginError) as ex:
                    logger.warning("[%s] Failed to post the purchase order %s.", worker_id, po.id)
                    logger.warning(ex)
                    po.set_status(PurchaseOrderStatus.failed)
                    po.status_details = str(ex)
                    po.when_changed = datetime.now()
                db.session.commit() #type: ignore
    except Exception as ex:
        logger.exception("[%s] Unexpected error processing customer %s POs", worker_id, username)
        for po in claimed_pos:
            if po.status == PurchaseOrderStatus.posting:
                po.set_status(PurchaseOrderStatus.failed)
                po.when_changed = datetime.now()
        db.session.commit() #type: ignore
        raise ex


@celery.task(bind=True)
def post_purchase_orders(self, po_id=None):
    logger = get_task_logger(__name__)
    logger.setLevel(current_app.config['LOG_LEVEL'])
    worker_id = self.request.id

    if po_id:
        # Atomically transition the requested PO from pending → posting BEFORE
        # acquiring the advisory lock.  This registers intent so that if another
        # worker already holds the lock for this customer, it will see this PO in
        # its "posting" loop and post it on our behalf.
        result = db.session.execute( #type: ignore
            update(PurchaseOrder)
            .where(PurchaseOrder.id == po_id,
                   PurchaseOrder.status == PurchaseOrderStatus.pending)
            .values(status=PurchaseOrderStatus.posting)
        )
        db.session.commit() #type: ignore
        if result.rowcount == 0:
            logger.info("[%s] PO %s is not in pending state, nothing to do", worker_id, po_id)
            return

        # Look up the customer username so we can name the advisory lock.
        username = db.session.execute( #type: ignore
            select(Subcustomer.username)
            .join(PurchaseOrder, PurchaseOrder.customer_id == Subcustomer.id)
            .where(PurchaseOrder.id == po_id)
        ).scalar_one_or_none()
        if not username:
            logger.warning("[%s] Could not find customer for PO %s", worker_id, po_id)
            return
        usernames = [username]
    else:
        # Batch mode (beat task): collect all customers that still have pending POs.
        usernames = db.session.execute( #type: ignore
            select(Subcustomer.username)
            .join(PurchaseOrder, PurchaseOrder.customer_id == Subcustomer.id)
            .where(PurchaseOrder.status == PurchaseOrderStatus.pending)
            .distinct()
        ).scalars().all()
        logger.info("[%s] Found %d customers with pending purchase orders",
                    worker_id, len(usernames))

    for username in usernames:
        lock_name = f'po_posting:{username}'
        # Use a dedicated connection for the advisory lock so it is held
        # independently of the working session's commit/rollback cycle.
        # MySQL automatically releases the lock when the connection closes,
        # so a crashed worker never leaves a username permanently locked.
        with db.engine.connect() as lock_conn:
            acquired = lock_conn.execute(
                text("SELECT GET_LOCK(:name, 0)"), {'name': lock_name}
            ).scalar()
            # Commit so SQLAlchemy's autobegun transaction is closed and the
            # cursor is fully finalised.  Without this MySQLdb raises
            # "Commands out of sync" (2014) on pool return.
            lock_conn.commit()

            if not acquired:
                if po_id:
                    # Our PO is already marked "posting"; the current lock holder
                    # will find it in its loop and post it for us.
                    logger.info("[%s] Customer %s is being processed by another worker; "
                                "PO %s is queued as 'posting' and will be picked up by "
                                "the lock holder", worker_id, username, po_id)
                else:
                    logger.info("[%s] Customer %s is already being processed by another "
                                "worker, skipping", worker_id, username)
                continue

            try:
                subcustomer = db.session.execute( #type: ignore
                    select(Subcustomer).where(Subcustomer.username == username)
                ).scalar_one_or_none()
                if not subcustomer:
                    logger.warning("[%s] Subcustomer not found for username %s",
                                   worker_id, username)
                    continue

                # Loop: keep posting until no "posting" POs remain for this customer.
                # Other tasks may pre-mark additional POs while we are busy here,
                # so we re-check after every batch.
                while True:
                    if not po_id:
                        # Batch mode: claim any remaining pending POs under the lock.
                        db.session.execute( #type: ignore
                            update(PurchaseOrder)
                            .where(
                                PurchaseOrder.customer_id == subcustomer.id,
                                PurchaseOrder.status == PurchaseOrderStatus.pending
                            )
                            .values(status=PurchaseOrderStatus.posting)
                        )
                        db.session.commit() #type: ignore

                    posting_pos = _get_posting_pos_for_customer(
                        subcustomer.id, worker_id, logger)
                    if not posting_pos:
                        logger.info("[%s] No more posting POs for customer %s",
                                    worker_id, username)
                        break

                    logger.info("[%s] Posting following POs for customer %s", worker_id, username)
                    logger.info("\n" + "\n".join([f"- {po.id}" for po in posting_pos]))
                    _post_claimed_pos(posting_pos, username, worker_id, logger)

            finally:
                lock_conn.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {'name': lock_name}
                ).scalar()
                lock_conn.commit()

    logger.info("[%s] Done posting purchase orders", worker_id)

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
            not_(PurchaseOrder.status.in_(( #type: ignore
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
    db.session.commit() #type: ignore
    logger.info("Done update of PO statuses")
