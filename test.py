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
    # with db.session.no_autoflush:
        po = PurchaseOrder.query.get('PO-2021-01-0015-001')
        po.status = PurchaseOrderStatus.pending
        po.vendor = 'AtomyQuick'
        po.company_id = 3
        # po.customer.username = '20589846'
        # po.customer.password = 'atom777'
        po.suborder.order_products[0].product = Product.query.get('834')
        po.suborder.order_products[0].product_id = '834'
        po.suborder.order_products[0].quantity = 5
        po.suborder.order_products[1].product = Product.query.get('875')
        po.suborder.order_products[1].product_id = '875'
        po.suborder.order_products[1].quantity = 5
        current_app.config['SELENIUM_BROWSER'] = 'localhost:9222'
        del current_app.config['SELENIUM_URL']
        # browser = Browser(config=current_app.config)
    #     vendor = PurchaseOrderVendorManager.get_vendor(
    #         po.vendor,
    #         browser=browser, config=current_app.config)
    #     vendor.post_purchase_order(po)
        post_purchase_orders(po_id='PO-2021-01-0015-001')
        # print(po.to_dict())
    # cProfile.run('build_network(root_id="S7882533", incremental=True)', filename='build_network.stat')
    # build_network(root_id='16222950', incremental=True)
    # copy_subtree(root_id='S9945812')
