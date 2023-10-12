import cProfile
from datetime import datetime

from app import db, create_app
from app.purchase.models import PurchaseOrder
from app.products.models import *
import logging
from app.import_products import get_atomy_products

from network_builder.build_network import build_network
logging.basicConfig(level=logging.DEBUG)
from app.jobs import *
from app.purchase.jobs import *

with create_app().app_context():
    # po_id = "PO-2023-03-0006-001"
    # po = PurchaseOrder.query.get(po_id)
    # po.status = PurchaseOrderStatus.pending
    # po.vendor = 'AtomyQuick'
    # po.company_id = 7
    # po.customer.username = '33095274'
    # po.customer.password = 'Irina1974!BE'
    # po.customer.username = 'S5832131'
    # po.customer.password = 'mkk03020529!!'
    # po.purchase_date = datetime(2023, 10, 4)
    # db.session.flush()
    # update_purchase_orders_status(po_id)
    # post_purchase_orders(po_id=po_id)
    # db.session.rollback()
    # print(po.to_dict())
    # cProfile.run('build_network(root_id="S7882533", incremental=True)', filename='build_network.stat')
    # build_network(user='S5832131', password='mkk030529!', incremental=True)
    # copy_subtree(root_id='S9945812')
    get_atomy_products()