def post_purchase_orders():
    from app.purchase.atomy import PurchaseOrderManager
    from app.purchase.models import PurchaseOrder, PurchaseOrderStatus

    logger = logging.getLogger(__name__)

    from app import create_app, db
    create_app().app_context().push()

    po_manager = PurchaseOrderManager(logger=logger)
    pending_purchase_orders = PurchaseOrder.query.filter_by(
        status=PurchaseOrderStatus.pending)
    logger.info("There are %s purchase orders to post", pending_purchase_orders.count())
    for po in pending_purchase_orders:
        logger.info("Posting a purchase order %s", po.id)
        try:
            po_manager.post_purchase_order(po)
            po.status = PurchaseOrderStatus.posted
            logger.info("Posted a purchase order %s", po.id)
        except Exception as ex:
            logger.exception("Failed to post the purchase order %s.", po.id)
            # logger.warning(ex)
            po.status = PurchaseOrderStatus.failed
        db.session.commit()
    logger.info('Done posting purchase orders')

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    post_purchase_orders()