from app import create_app
from app.purchase.models import PurchaseOrder
from app.purchase.atomy import PurchaseOrderManager
from app.orders.models import Subcustomer
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)
from app.utils.atomy import atomy_login
from app.jobs import *

with create_app().app_context():
    update_purchase_orders_status(Browser(headless=False, connect_to="localhost:9222"))
    # pom = PurchaseOrderManager(
	# 	 Browser(headless=False, connect_to="localhost:9222"), 
	# 	 logging.getLogger('pom'))
    # subcustomer = Subcustomer.query.get(36)
    # pom.update_purchase_orders_status(subcustomer)
    # po = PurchaseOrder.query.get('PO-2020-10-0022-009')
    # po.customer.password = '1'
    # pom.update_purchase_order_status(po)
    # pom.post_purchase_order(po)
# atomy_login('11305301', 's111111!', Browser(headless=False))
# atomy_login('12170778', 's111111!', Browser(headless=False))
