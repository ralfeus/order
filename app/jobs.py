from datetime import datetime
from more_itertools import map_reduce
from time import sleep

from flask import current_app
from sqlalchemy import not_

from app import celery, db

def import_products():
    from app import create_app
    from app.import_products import atomy
    from app.products.models import Product
    
    create_app().app_context().push()
    current_app.logger.info('Starting products import')
    products = Product.query.all()
    same = new = modified = ignored = 0
    for atomy_product in atomy():
        try:
            product = next(p for p in products
                           if p.id.lstrip('0') == atomy_product['id'].lstrip('0'))
            if product.synchronize:
                is_dirty = False
                if product.name != atomy_product['name']:
                    product.name = atomy_product['name']
                    is_dirty = True
                if product.price != int(atomy_product['price']):
                    product.price = int(atomy_product['price'])
                    is_dirty = True
                if product.points != int(atomy_product['points']):
                    product.points = int(atomy_product['points'])
                    is_dirty = True
                if product.available != atomy_product['available']:
                    product.available = atomy_product['available']
                    is_dirty = True
                if is_dirty:
                    product.when_changed = datetime.now()
                    modified += 1
                else:
                    same += 1
            else:
                ignored += 1

            products.remove(product)
        except StopIteration:
            product = Product(
                id=atomy_product['id'],
                name=atomy_product['name'],
                price=atomy_product['price'],
                points=atomy_product['points'],
                weight=0,
                available=atomy_product['available'],
                when_created=datetime.now()
            )
            new += 1
            db.session.add(product)
    for product in products:
        if product.synchronize:
            product.available = False
            modified += 1
        else:
            ignored += 1
    current_app.logger.info(f"""Product synchronization result:
                                same: {same}, new: {new},
                                modified: {modified}, ignored: {ignored}""")
    db.session.commit()

# @celery.on_after_finalize.connect
# def setup_periodic_tasks(sender, **kwargs):
#     sender.add_periodic_task(3600, update_purchase_orders_status,
#         name='Update PO status every 60 minutes')


@celery.task
def add_together(a, b):
    for i in range(100):
        sleep(1)
    return a + b

@celery.task
def post_purchase_orders(po_id=None):
    from app.orders.models import OrderProduct
    from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
    pending_purchase_orders = PurchaseOrder.query
    if po_id:
        pending_purchase_orders = pending_purchase_orders.filter_by(id=po_id)
    pending_purchase_orders = pending_purchase_orders.filter_by(
        status=PurchaseOrderStatus.pending)
    try: 
        # Wrap whole operation in order to 
        # mark all pending POs as failed in case of any failure
        from celery.utils.log import get_task_logger
        logger = get_task_logger(__name__)

        from app.purchase.atomy import PurchaseOrderManager
        po_manager = PurchaseOrderManager(logger=logger)

        logger.info("There are %s purchase orders to post", pending_purchase_orders.count())
        for po in pending_purchase_orders:
            logger.info("Posting a purchase order %s", po.id)
            try:
                po_manager.post_purchase_order(po)
                posted_orders_count = po.order_products.filter_by(status='Purchased').count()
                if posted_orders_count == po.order_products.count():
                    po.status = PurchaseOrderStatus.posted
                elif posted_orders_count > 0:
                    po.status = PurchaseOrderStatus.partially_posted
                else:
                    po.status = PurchaseOrderStatus.failed
                    logger.warning("Purchase order %s posting went successfully but no products were ordered", po.id)
                logger.info("Posted a purchase order %s", po.id)
            except Exception as ex:
                logger.exception("Failed to post the purchase order %s.", po.id)
                # logger.warning(ex)
                po.status = PurchaseOrderStatus.failed
                po.status_details = str(ex)
            db.session.commit()
        logger.info('Done posting purchase orders')
    except Exception as ex:
        for po in pending_purchase_orders:
            po.status = PurchaseOrderStatus.failed
        db.session.commit()
        raise ex

@celery.task
def update_purchase_orders_status(po_id=None, browser=None):
    from celery.utils.log import get_task_logger
    from app.orders.models import Subcustomer
    from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
    from app.purchase.atomy import PurchaseOrderManager
    
    logger = get_task_logger(__name__)
    logger.info("Starting update of PO statuses")
    po_manager = PurchaseOrderManager(logger=logger, browser=browser)
    pending_purchase_orders = PurchaseOrder.query
    if po_id:
        pending_purchase_orders = pending_purchase_orders.filter_by(id=po_id)
    else:
        pending_purchase_orders = pending_purchase_orders.filter(
            not_(PurchaseOrder.status.in_((
                PurchaseOrderStatus.cancelled,
                PurchaseOrderStatus.failed,
                PurchaseOrderStatus.shipped)))
        )
    grouped_customers = map_reduce(
        pending_purchase_orders,
        lambda po: po.customer)
    for customer, purchase_orders in grouped_customers.items():
        try:
            logger.info("Updating subcustomer %s", customer.name)
            po_manager.update_purchase_orders_status(customer, purchase_orders)
        except:
            logger.exception(
                "Couldn't update POs status for %s", customer.name)
    db.session.commit()
    logger.info("Done update of PO statuses")