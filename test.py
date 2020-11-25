from app import create_app
from app.purchase.models import PurchaseOrder
from app.orders.models import Subcustomer
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)
from app.utils.atomy import atomy_login
from app.jobs import *
from app.purchase.jobs import *

with create_app().app_context():
    PurchaseOrder.query.get('PO-2020-11-0002-001').status = PurchaseOrderStatus.pending
    post_purchase_orders(po_id='PO-2020-11-0002-001')