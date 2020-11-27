from app import create_app
from app.purchase.models import PurchaseOrder
from app.orders.models import Subcustomer
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)
from app.jobs import *
from app.purchase.jobs import *

with create_app().app_context():
    po = PurchaseOrder.query.get('PO-2020-11-0002-001')
    po.status = PurchaseOrderStatus.pending
    browser = Browser(connect_to='localhost:9222')
    vendor = PurchaseOrderVendorManager.get_vendor(
        po.vendor, logger=logging.getLogger(),
        browser=browser)
    vendor.post_purchase_order(po)