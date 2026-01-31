from datetime import date, datetime
import sys
import logging

from app import db, create_app
from app.purchase.models import PurchaseOrder
from app.products.models import *

from app.jobs import *
from app.purchase.jobs import *
from app.tools import invoke_curl
import threading
import time
# logging.basicConfig(level=logging.INFO)

def build_network():
    sys.path.append('./network_builder')
    from network_builder.build_network import build_network
    build_network(user='S5832131', password='mkk03020529!!', max_threads=1, 
                  last_updated=date(2030, 1, 4), profile=False) #, root_id='44300050'
    # copy_subtree(root_id='S9945812')
    # cleanup_tree(date(2024, 11, 21), user='S5832131', password='mkk03020529!!', threads=50)

    # get_atomy_products()

def post_po():
    # from flask import current_app
    # current_app.config['SOCKS5_PROXY'] = 'localhost:9050'
    current_app.config['BROWSER_URL'] = 'http://localhost:9222'
    po_id = "PO-2026-01-0001-001"
    po = PurchaseOrder.query.get(po_id)
    po.status = PurchaseOrderStatus.pending
    # po.vendor = 'AtomyQuick'
    # po.company_id = 4
    po.customer.username = '23426444'
    po.customer.password = 'atomy#01'     
    po.purchase_date = datetime.now()
    db.session.flush()
    post_purchase_orders(po_id=po_id)

    db.session.rollback()
    # print(po.to_dict())

def test_multiple_login():

    from app.orders.models.subcustomer import Subcustomer
    from utils import get_json
    from utils.atomy import atomy_login2
    subcustomers = Subcustomer.query.limit(50).all()
    tokens = {}

    for subcustomer in subcustomers:
        try:
            token = atomy_login2(subcustomer.username, subcustomer.password)
            tokens[subcustomer.username] = token
        except:
            print("Couldn't log in as ", subcustomer.username)
    TREE_URL = 'https://shop-api-ga.atomy.com/svc/genealogyTree/getGenealogyTree'
    DATA_TEMPLATE = "custNo={}&standardDate={}&startDate={}&endDate={}&level=100&dataType=include&_siteId=kr&_deviceType=pc&locale=ko-KR"
    today = datetime.today()
    start_date = today.strftime('%Y%m01' if today.day < 16 else '%Y%m16')
    for user,token in tokens.items():
        try:
            page = get_json(TREE_URL + '?' + 
                    DATA_TEMPLATE.format(user, start_date, start_date, start_date), 
                    headers=[{'Cookie': tokens['16814614']}])
            print(user, len(page['items']['includeItems']))
        except Exception as e:
            if str(e) == '나의 하위회원 계보도만 조회 가능합니다.':
                pass
            else:
                print(page)

def test_login():
    from utils.atomy import atomy_login2
    atomy_login2('23426444', 'atomy#01')
    atomy_login2('44315585', 'Magnit135!') 

threads = 0
def copy_password_to_graph():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('neo4j').setLevel(logging.INFO)
    logging.getLogger('utils.atomy').setLevel(logging.WARNING)
    def test_login(username, password):
        global threads
        try:
            atomy_login2(username, password, socks5_proxy='localhost:9050')
            result, _ = db.cypher_query("""
                MATCH (n:AtomyPerson {atomy_id: $username}) 
                SET n.username = $username, n.password = $password
                """, {'username': username, 'password': password})
        except AtomyLoginError:
            pass
        with lock:
            threads -= 1
    import os
    from app.orders.models.subcustomer import Subcustomer
    from neomodel import db, config
    from utils.atomy import atomy_login2
    config.DATABASE_URL = os.environ.get('NEO4J_URL') or 'bolt://neo4j:1@localhost:7687'
    subcustomers = Subcustomer.query.all()
    lock = threading.Lock()
    global threads
    for subcustomer in tqdm(subcustomers):
        while threads >= 50:
            time.sleep(1)
        with lock:
            threads += 1
        threading.Thread(target=test_login,
                         args=[subcustomer.username, subcustomer.password]) \
            .start()

def multiple_request():
    from utils.atomy import atomy_login2
    from utils import get_json
    token = atomy_login2('23426444', 'atomy#01')
    TREE_URL = 'https://kr.atomy.com/myoffice/genealogy/tree'
    DATA_TEMPLATE = "level=100&dropYn=Y&otherCustNo=23426444"
    for i in range(20):
        res = get_json(url=TREE_URL + '?' + DATA_TEMPLATE,
                headers=[{'Cookie': token}, {'Cookie': 'KR_language=en'}])
        print(len(res.keys()) if type(res) == dict else len(res))
        time.sleep(.8)
############################# Entry point #####################################

def import_products():
    from app.jobs import import_products
    current_app.config['PRODUCT_IMPORT_URL'] = 'https://tr.atomy.com'
    import_products()

with create_app().app_context():
    logging.root.setLevel(logging.DEBUG)
    post_po()
    # import_products()
    # build_network()
