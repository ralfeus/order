from datetime import datetime
from flask import current_app
from app import create_app
from app.purchase.models import PurchaseOrder
from app.orders.models import Subcustomer
from app.utils.browser import Browser
import logging
# logging.basicConfig(level=logging.DEBUG)
from app.jobs import *
from network_builder.build_network import build_network
from app.purchase.jobs import *
import cProfile

with create_app().app_context():
    # po = PurchaseOrder.query.get('PO-2021-01-0015-001')
    # po.status = PurchaseOrderStatus.pending
    # po.customer.username = '25596031'
    # po.customer.password = '1234567Kz$'
    # current_app.config['SELENIUM_BROWSER'] = 'localhost:9222'
    # del current_app.config['SELENIUM_URL']
    # browser = Browser(config=current_app.config)
    # vendor = PurchaseOrderVendorManager.get_vendor(
    #     po.vendor, logger=logging.getLogger(),
    #     browser=browser)
    # vendor.post_purchase_order(po)
    # post_purchase_orders(po_id='PO-2021-01-0015-001')
    # print(po.to_dict())
    # cProfile.run('build_network(update=False, incremental=True)', filename='build_network.stat')
    build_network(root_id='11888056')
    # copy_subtree(root_id='S9945812')
