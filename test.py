from app import create_app
from app.purchase.models import PurchaseOrder
from app.purchase.atomy import PurchaseOrderManager
from app.utils.browser import Browser
import logging
logging.basicConfig(level=logging.DEBUG)
from app.utils.atomy import atomy_login

with create_app().app_context():
	pom = PurchaseOrderManager(Browser(headless=False), logging.getLogger('pom'))
	po = PurchaseOrder.query.get('ORD-2020-10-0008-000019')
	pom.post_purchase_order(po)
# atomy_login('11305301', 's111111!', Browser(headless=False))   
# atomy_login('12170778', 's111111!', Browser(headless=False))   
