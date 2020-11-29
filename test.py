from flask import current_app
from app import create_app
from app.purchase.models import PurchaseOrder
from app.orders.models import Subcustomer
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)
from app.jobs import *
from app.purchase.jobs import *

with create_app().app_context():
    po = PurchaseOrder.query.get('PO-2020-10-0023-001')
    po.status = PurchaseOrderStatus.pending
    # current_app.config['SELENIUM_BROWSER'] = 'localhost:9222'
    browser = Browser(config=current_app.config)
    vendor = PurchaseOrderVendorManager.get_vendor(
        po.vendor, logger=logging.getLogger(),
        browser=browser)
    vendor.post_purchase_order(po)
    print(po.to_dict())