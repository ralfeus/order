import cProfile
from datetime import datetime
import random
import sys

from app import db, create_app
from app.purchase.models import PurchaseOrder
from app.products.models import *
import logging
from app.import_products import get_atomy_products

logging.basicConfig(level=logging.DEBUG)
from app.jobs import *
from app.purchase.jobs import *
from app.tools import invoke_curl
import threading
import time

with create_app().app_context():
    # po_id = "PO-2024-06-0001-001"
    # po = PurchaseOrder.query.get(po_id)
    # po.status = PurchaseOrderStatus.pending
    # po.vendor = 'AtomyQuick'
    # po.company_id = 7
    # po.customer.username = 'S5832131'
    # po.customer.password = 'mkk03020529!!'
    # po.purchase_date = datetime.now()
    # db.session.flush()
    # post_purchase_orders(po_id=po_id)
    # db.session.rollback()
    # print(po.to_dict())

    sys.path.append('./network_builder')
    from network_builder.build_network import build_network
    # cProfile.run('build_network(root_id="S7882533", incremental=True)', filename='build_network.stat')
    build_network(user='S5832131', password='mkk03020529!!', threads=1)
    # copy_subtree(root_id='S9945812')

    # get_atomy_products()
