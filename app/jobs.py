from datetime import datetime
from logging import RootLogger
from more_itertools import map_reduce
import re
from time import sleep
from celery.utils.log import get_task_logger
from lxml.cssselect import CSSSelector
from sqlalchemy import or_
from tqdm import tqdm

from app import celery, db
from app.exceptions import AtomyLoginError
from app.network.models.node import Node

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(28800, import_products,
        name="Import products from Atomy every 8 hours")
    # sender.add_periodic_task(crontab(hour=16, minute=0), post_purchase_orders,
    #     name="Run pending POs every day")

@celery.task
def import_products():
    from app.import_products import get_atomy_products
    from app.products.models import Product
    
    logger = get_task_logger(__name__)
    logger.info("Starting products import")
    products = Product.query.all()
    same = new = modified = ignored = 0
    vendor_products = get_atomy_products()
    logger.info("Got %d products", len(vendor_products))
    if len(vendor_products) == 0: # Something went wrong
        logger.warning("Something went wrong. Didn't get any products from vendor. Exiting...")
        return
    for atomy_product in vendor_products:
        try:
            product = next(p for p in products
                           if p.id.lstrip('0') == atomy_product['id'].lstrip('0'))
            if product.synchronize:
                logger.debug('Synchronizing product %s', atomy_product['id'])
                is_dirty = False
                if product.name != atomy_product['name']:
                    logger.debug('\tname(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['name'], product.name)
                    product.name = atomy_product['name']
                    is_dirty = True
                if product.price != int(atomy_product['price']):
                    logger.debug('\tprice(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['price'], product.price)
                    product.price = int(atomy_product['price'])
                    is_dirty = True
                if product.points != int(atomy_product['points']):
                    logger.debug('\tpoints(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['points'], product.points)
                    product.points = int(atomy_product['points'])
                    is_dirty = True
                if product.available != atomy_product['available']:
                    logger.debug('\tavailable(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['available'], product.available)
                    product.available = atomy_product['available']
                    is_dirty = True
                if is_dirty:
                    logger.debug('\t%s: MODIFIED', atomy_product['id'])
                    product.when_changed = datetime.now()
                    modified += 1
                else:
                    logger.debug('\t%s: SAME', atomy_product['id'])
                    same += 1
            else:
                logger.debug('\t%s: IGNORED', product.id)
                ignored += 1

            products.remove(product)
        except StopIteration:
            logger.debug('%s: No local product found. ADDING', atomy_product['id'])
            product = Product(
                id=atomy_product['id'],
                name=atomy_product['name'],
                price=atomy_product['price'],
                points=atomy_product['points'],
                weight=0,
                available=atomy_product['available'],
                when_created=datetime.now()
            )
            new += 1
            db.session.add(product)
    logger.debug('%d local products left without matching vendor\'s ones. Will be disabled',
        len(products))
    for product in products:
        if product.synchronize:
            logger.debug("%s: should be synchronized. DISABLED", product.id)
            product.available = False
            modified += 1
        else:
            logger.debug("%s: should NOT be synchronized. IGNORED", product.id)
            ignored += 1
    logger.info(
        "Product synchronization result: same: %d, new: %d, modified: %d, ignored: %d",
        same, new, modified, ignored)
    db.session.commit()

sel_name = CSSSelector('td span:nth-child(2)')
sel_rank = CSSSelector('td span:nth-child(3)')
sel_highest_rank = CSSSelector('td span:nth-child(4)')
sel_center = CSSSelector('td span:nth-child(5)')
sel_country = CSSSelector('td span:nth-child(6)')
sel_signup_date = CSSSelector('td span:nth-child(7)')
sel_pv = CSSSelector('td span:nth-child(8)')
sel_network_pv = CSSSelector('td span:nth-child(9)')

@celery.task
def build_network(username='S5832131', password='mkk03020529!', root='S5832131',
    update=False, incremental=False):
    from app.utils.atomy import atomy_login, get_document_from_url

    sel_members = CSSSelector('div#dLine table')
    session_cookies = atomy_login(username=username, password=password, run_browser=False)
    # add_session = sessionmaker(bind=db.session.bind)()
    tree_url = 'https://www.atomy.kr/v2/Home/MyAtomy/GroupTree2'
    data_template = "Slevel={}&VcustNo={}&VbuCustName=0&VgjisaCode=1&VgmemberAuth=0&VglevelCnt=0&Vglevel=1&VglevelMax=1&VgregDate=1&VgcustDate=0&VgstopDate=0&VgtotSale=1&VgcumSale=0&VgcurSale=1&VgbuName=1&SDate=2021-02-23&EDate=2021-02-23&glevel=1&glevelMax=1&gbu_name=1&gjisaCode=1&greg_date=1&gtot_sale=1&gcur_sale=1"
    if update:
        nodes = []
        traversing_nodes = [Node.query.get(root)]
    else:
        nodes, traversing_nodes = _init_network(root, incremental=incremental)
    c = 0
    traversing_nodes_set = set(traversing_nodes)
    try:
        for node in traversing_nodes:
            c += 1
            print(f"{c} of {len(traversing_nodes)}", end="\r")
            for levels in [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]:
                while True:
                    try:
                        page = get_document_from_url(tree_url,
                            headers=[{'Cookie': c} for c in session_cookies],
                            raw_data=data_template.format(levels, node.id))
                        break
                    except AtomyLoginError:
                        print("Session expired. Logging in...")
                        session_cookies = atomy_login(
                            username=username, password=password, run_browser=False)
                members = sel_members(page)
                if len(members) > 0:
                    last_level_top = max(map_reduce(
                        members,
                        keyfunc=lambda m: int(_get_element_style_items(m)['top'][:-2])
                    ).keys())
                    if update:
                        _update_nodes(c, traversing_nodes, members, last_level_top)
                    else:
                        _get_children(
                            node, c, traversing_nodes, traversing_nodes_set, members[0], 
                            members[1:],
                            level_distance=_get_levels_distance(members),
                            last_level_top=last_level_top
                        )
                    db.session.commit()
                    break
                print(f"\nCouldn't get {levels} levels. Decreasing...")
    except Exception as ex:
        raise ex
    nodes += traversing_nodes
    # print(nodes)
    print("Total %s items" % len(nodes))

def _get_children(node, current_node, traversing_nodes, tn_search, node_element,
    elements, level_distance, last_level_top):
    node_element_style_items = _get_element_style_items(node_element)
    node_element_top = int(node_element_style_items['top'][:-2])
    node_element_left = int(node_element_style_items['left'][:-2])
    next_layer_top = node_element_top + level_distance
    next_layer_elements = [e for e in elements
                           if int(_get_element_style_items(e)['top'][:-2]) == next_layer_top]
    left = right = left_element = right_element = None
    is_left_found = False
    for element in sorted(
        next_layer_elements, key=lambda e: int(_get_element_style_items(e)['left'][:-2])):
        element_id = element.attrib['id'][1:]
        if is_left_found:
            right = _get_node(element, node, False)
            right_element = element
            break
        if int(_get_element_style_items(element)['left'][:-2]) == node_element_left:
            left = _get_node(element, node, True)
            left_element = element
            break
        if int(_get_element_style_items(element)['left'][:-2]) > node_element_left:
            break
        if int(_get_element_style_items(element)['left'][:-2]) < node_element_left:
            # if len([e for e in nodes + traversing_nodes
            #         if e.id == element_id]) == 0:
            if not Node.query.get(element_id):
                left = _get_node(element, node, True)
                left_element = element
                is_left_found = True
    if node_element_top == last_level_top and len(elements) != 0:
        # if len([e for e in traversing_nodes if e.id == node.id]) == 0:
        if node not in tn_search:
            tn_search.add(node)
            traversing_nodes.append(node)
            node.built_tree = False
            # db.session.add(node)
    else:
        # if len([e for e in traversing_nodes if e.id == node.id]) == 0:
        # if node not in traversing_nodes:
            # nodes.append(node)
            # db.session.add(node)
        node.built_tree = True
        if left is not None:
            _get_children(left, current_node, traversing_nodes, tn_search, left_element, elements,
                level_distance=level_distance, last_level_top=last_level_top)
        if right is not None:
            _get_children(right, current_node, traversing_nodes, tn_search, right_element, elements,
            level_distance=level_distance, last_level_top=last_level_top)

def _get_element_style_items(element):
    style_items = element.attrib['style'].split(';')
    dict_style_items = {e.split(':')[0].strip(): e.split(':')[1].strip() 
                        for e in style_items
                        if ':' in e}
    return dict_style_items

def _get_levels_distance(members):
    if len(members) <= 1:
        return 0
    first_level = int(_get_element_style_items(members[0])['top'][:-2])
    second_level = int(_get_element_style_items(members[1])['top'][:-2])
    return second_level - first_level

def _init_network(root_node_id, incremental=True):
    db.create_all()
    traversing_nodes_query = Node.query.filter_by(built_tree=False) \
        if incremental \
        else Node.query.filter_by(left_id=None, right_id=None) 
    if traversing_nodes_query.count() > 0:
        traversing_nodes = traversing_nodes_query.all()
    else:
        root_node = Node(id=root_node_id)
        traversing_nodes = [root_node]
        db.session.add(root_node)
        db.session.commit()
    nodes = Node.query.filter_by(built_tree=True) \
        if incremental \
        else Node.query.filter(or_(Node.left_id != None, Node.right_id != None)).all()
    return nodes, traversing_nodes

def _get_node(element, parent, is_left):
    id = element.attrib['id'][1:]
    node = Node(
        id=id, parent_id=parent.id,
        name=sel_name(element)[0].text,
        rank=sel_rank(element)[0].text,
        highest_rank=sel_highest_rank(element)[0].text,
        center=sel_center(element)[0].text,
        country=sel_country(element)[0].text,
        signup_date=sel_signup_date(element)[0].text,
        pv=int(re.search('\\d+', sel_pv(element)[0].text).group()),
        network_pv=int(re.search('\\d+', sel_network_pv(element)[0].text).group())
    )
    db.session.add(node)
    db.session.flush()
    if is_left:
        parent.left_id = id
    else:
        parent.right_id = id
    return node

def _update_nodes(current_node, traversing_nodes, elements, last_level_top):
    desc = f"Traversing node {current_node} of {len(traversing_nodes)}"
    for element in tqdm(elements, desc=desc):
        # node = [n for n in nodes if n.id == element.attrib['id'][1:]][0]
        node = Node.query.get(element.attrib['id'][1:])
        if node:
            node.rank = sel_rank(element)[0].text
            node.highest_rank = sel_highest_rank(element)[0].text
            node.pv = re.search('\\d+', sel_pv(element)[0].text).group()
            node.network_pv = re.search('\\d+', sel_network_pv(element)[0].text).group()
            if int(_get_element_style_items(element)['top'][:-2]) == last_level_top:
                traversing_nodes.append(node)

@celery.task
def add_together(a, b):
#    for i in range(100):
#        sleep(1)
    return a + b

