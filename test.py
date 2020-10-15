from app import create_app
from app.purchase.models import PurchaseOrder
from app.purchase.atomy import PurchaseOrderManager
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)

with create_app().app_context():
	pom = PurchaseOrderManager(Browser(headless=False), logging.getLogger('pom'))
	po = PurchaseOrder.query.get('ORD-2020-09-0012-000006')
	pom.post_purchase_order(po)
