import cProfile
from datetime import date, datetime
import random
import sys

from app import db, create_app
from app.purchase.models import PurchaseOrder
from app.products.models import *
from app.import_products import get_atomy_products

from app.jobs import *
from app.purchase.jobs import *
from app.tools import invoke_curl
import threading
import time

def debug():
    po_id = "PO-2024-06-0001-001"
    po = PurchaseOrder.query.get(po_id)
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
    build_network(user='S5832131', password='mkk03020529!!', threads=60)
    # copy_subtree(root_id='S9945812')
    # cleanup_tree(date(2024, 11, 21), user='S5832131', password='mkk03020529!!', threads=50)

    # get_atomy_products()


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

def copy_password_to_graph():
    logging.basicConfig(level=logging.INFO)
    def test_login(username, password):
        try:
            atomy_login2(username, password, socks5_proxy='127.0.0.1:9050')
            result, _ = db.cypher_query("""
                MATCH (n:AtomyPerson {atomy_id: $username}) 
                SET n.password = $password
                """, {'username': username, 'password': password})
        except AtomyLoginError:
            pass
    import os
    from app.orders.models.subcustomer import Subcustomer
    from neomodel import db, config
    from utils.atomy import atomy_login2
    config.DATABASE_URL = os.environ.get('NEO4J_URL') or 'bolt://neo4j:1@localhost:7687'
    subcustomers = Subcustomer.query.all()
    for subcustomer in tqdm(subcustomers):
        while threading.active_count() - 2 >= 100:
            time.sleep(1)
        threading.Thread(target=test_login, 
                         args=[subcustomer.username, subcustomer.password]) \
            .start()
############################# Entry point #####################################

with create_app().app_context():
    copy_password_to_graph()