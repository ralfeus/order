from datetime import datetime
from flask import current_app
from app import db, create_app
from app.purchase.models import PurchaseOrder
from app.orders.models import Subcustomer
from app.products.models import *
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)
from app.jobs import *
from network_builder.build_network import build_network
from app.purchase.jobs import *
import cProfile

with create_app().app_context():
    po = PurchaseOrder.query.get('PO-2021-04-0002-001')
    po.status = PurchaseOrderStatus.pending
    po.vendor = 'AtomyQuick'
    po.company_id = 4
    po.customer.username = '23426444'
    po.customer.password = 'atomy#01'
    po.purchase_restricted_products = True
    db.session.flush()
    # current_app.config['SELENIUM_BROWSER'] = 'localhost:9222'
    # del current_app.config['SELENIUM_URL']
    # update_purchase_orders_status('PO-2021-03-0001-001')
    # browser = Browser(config=current_app.config)
#     vendor = PurchaseOrderVendorManager.get_vendor(
#         po.vendor,5
#         browser=browser, config=current_app.config)
#     vendor.post_purchase_order(po)
    post_purchase_orders(po_id='PO-2021-04-0002-001')
    db.session.rollback()
    # print(po.to_dict())
    # cProfile.run('build_network(root_id="S7882533", incremental=True)', filename='build_network.stat')
    # build_network(incremental=True)
    # copy_subtree(root_id='S9945812')
