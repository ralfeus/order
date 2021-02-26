from datetime import datetime
from more_itertools import map_reduce
import logging
from lxml.cssselect import CSSSelector
import os
import re
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import Session

from app.exceptions import AtomyLoginError
from app.network.models.node import Node

sel_name = CSSSelector('td span:nth-child(2)')
sel_rank = CSSSelector('td span:nth-child(3)')
sel_highest_rank = CSSSelector('td span:nth-child(4)')
sel_center = CSSSelector('td span:nth-child(5)')
sel_country = CSSSelector('td span:nth-child(6)')
sel_members = CSSSelector('div#dLine table')
sel_signup_date = CSSSelector('td span:nth-child(7)')
sel_pv = CSSSelector('td span:nth-child(8)')
sel_network_pv = CSSSelector('td span:nth-child(9)')

db_host = os.environ.get('DB_HOST') or 'localhost'
db_user = os.environ.get('DB_USER') or 'omc'
db_password = os.environ.get('DB_PASSWORD') or 'omc'
db_db = os.environ.get('DB_DB') or 'order_master_common'
engine = create_engine(
    f"mysql+mysqldb://{db_user}:{db_password}@{db_host}/{db_db}?auth_plugin=mysql_native_password&charset=utf8")
session = Session(engine)
logging.basicConfig(level=logging.INFO)

def build_network(username='S5832131', password='mkk03020529!', root_id='S5832131',
    update=False, incremental=False, cont=False):
    from app.utils.atomy import atomy_login, get_document_from_url
    logger = logging.getLogger('build_network')
    logger.info("Logging in to Atomy")
    session_cookies = atomy_login(username=username, password=password, run_browser=False)
    tree_url = 'https://www.atomy.kr/v2/Home/MyAtomy/GroupTree2'
    data_template = "Slevel={}&VcustNo={}&VbuCustName=0&VgjisaCode=1&VgmemberAuth=0&VglevelCnt=0&Vglevel=1&VglevelMax=1&VgregDate=1&VgcustDate=0&VgstopDate=0&VgtotSale=1&VgcumSale=0&VgcurSale=1&VgbuName=1&SDate=2021-02-23&EDate=2021-02-23&glevel=1&glevelMax=1&gbu_name=1&gjisaCode=1&greg_date=1&gtot_sale=1&gcur_sale=1"
    if cont or incremental:
        traversing_nodes = _init_network(root_id, incremental=incremental, cont=cont)
    else:
        root_node = session.query(Node).get(root_id)
        if not root_node:
            raise Exception(f'No node {root_id} is in tree')
        traversing_nodes = [root_node]
    c = 0
    try:
        for node in traversing_nodes:
            c += 1
            logger.info("%s of %s", c, len(traversing_nodes))
            for levels in [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]:
                while True:
                    try:
                        page = get_document_from_url(tree_url,
                            headers=[{'Cookie': c} for c in session_cookies],
                            raw_data=data_template.format(levels, node.id))
                        break
                    except AtomyLoginError:
                        logger.info("Session expired. Logging in")
                        session_cookies = atomy_login(
                            username=username, password=password, run_browser=False)
                    except Exception as ex:
                        logger.error("Something bad has happened")
                        logger.error(tree_url, session_cookies, node.id)
                        raise ex
                members = sel_members(page)
                if len(members) > 0:
                    logger.debug("Got %s levels. Processing", levels)
                    last_level_top = max(map_reduce(
                        members,
                        keyfunc=lambda m: int(_get_element_style_items(m)['top'][:-2])
                    ).keys())
                    if update:
                        _update_nodes(c, traversing_nodes, members, last_level_top)
                    else:
                        _get_children(
                            node, c, traversing_nodes, members[0], members[1:],
                            level_distance=_get_levels_distance(members),
                            last_level_top=last_level_top
                        )
                    session.commit()
                    break
                logger.debug("Couldn't get %s levels. Decreasing", levels)
            # if c == 50:
            #     break
    except Exception as ex:
        raise ex
    logger.info("Done.")

def _get_children(node, current_node, traversing_nodes, node_element,
    elements, level_distance, last_level_top, page_nodes=set()):
    page_nodes.add(node.id)
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
            if element_id not in page_nodes:
                left = _get_node(element, node, True)
                left_element = element
                is_left_found = True
    if node_element_top == last_level_top and len(elements) != 0:
        # if node.id not in page_nodes:
            traversing_nodes.append(node)
            node.built_tree = False
    else:
        node.built_tree = True
        if left is not None:
            _get_children(left, current_node, traversing_nodes, left_element, elements,
                level_distance=level_distance, last_level_top=last_level_top,
                page_nodes=page_nodes)
        if right is not None:
            _get_children(right, current_node, traversing_nodes, right_element, elements,
                level_distance=level_distance, last_level_top=last_level_top,
                page_nodes=page_nodes)

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

def _init_network(root_node_id, incremental=False, cont=False):
    logger = logging.getLogger("_init_network")
    if incremental:
        logger.info("Resetting leafs progress")
        session.execute('''
            UPDATE network_nodes
            SET built_tree = 0 
            WHERE left_id IS NULL AND right_id IS NULL
        ''')
    logger.info("Getting leafs to crawl")
    traversing_nodes_query = \
        session.query(Node).filter_by(built_tree=False) if cont \
        else session.query(Node).filter_by(left_id=None, right_id=None) if incremental \
        else None
    if traversing_nodes_query and traversing_nodes_query.count() > 0:
        traversing_nodes = traversing_nodes_query.all()
    else:
        root_node = Node(id=root_node_id)
        traversing_nodes = [root_node]
        session.add(root_node)
        session.commit()
    # nodes = Node.query.filter_by(built_tree=True) \
    #     if incremental \
    #     else Node.query.filter(or_(Node.left_id != None, Node.right_id != None)).all()
    logger.info("Done")
    return traversing_nodes

def _get_node(element, parent, is_left):
    from time import sleep
    logger = logging.getLogger('_get_node')
    id = element.attrib['id'][1:]
    node = Node(
        id=id, parent_id=parent.id,
        name=sel_name(element)[0].text,
        rank=sel_rank(element)[0].text,
        highest_rank=sel_highest_rank(element)[0].text,
        center=sel_center(element)[0].text,
        country=sel_country(element)[0].text,
        signup_date=datetime.strptime(sel_signup_date(element)[0].text, '%y-%m-%d'),
        pv=int(re.search('\\d+', sel_pv(element)[0].text).group()),
        network_pv=int(re.search('\\d+', sel_network_pv(element)[0].text).group())
    )
    session.add(node)
    try:
        session.flush()
    except UnicodeEncodeError as ex:
        logger.error("Couldn't add object %s", node.to_dict())
        logger.error(ex)
        raise ex
    if is_left:
        parent.left_id = id
    else:
        parent.right_id = id
    return node

def _update_nodes(current_node, traversing_nodes, elements, last_level_top):
    logger = logging.getLogger('_update_nodes')
    logger.info("Traversing node %s of %s", current_node, len(traversing_nodes))
    for element in elements:
        # node = [n for n in nodes if n.id == element.attrib['id'][1:]][0]
        node = session.query(Node).get(element.attrib['id'][1:])
        if node:
            node.rank = sel_rank(element)[0].text
            node.highest_rank = sel_highest_rank(element)[0].text
            node.pv = re.search('\\d+', sel_pv(element)[0].text).group()
            node.network_pv = re.search('\\d+', sel_network_pv(element)[0].text).group()
            if int(_get_element_style_items(element)['top'][:-2]) == last_level_top:
                traversing_nodes.append(node)


if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description="Build network")
    group = arg_parser.add_mutually_exclusive_group()
    group.add_argument('--root', metavar='ROOT_ID', help="ID of the tree or subtree root")
    group.add_argument('--update', help='Update data of existing nodes', action='store_true')
    group.add_argument('--incremental', help='Build trees from all leaves',
                    action='store_true')
    group.add_argument('--continue', dest='cont',
                    help='Continue tree building after being interrupted', action='store_true')
    args = arg_parser.parse_args()
    args.incremental = not (args.update or args.cont or args.root)

    logging.info('Building tree with following arguments: %s', args)

    build_network(
        root_id=args.root, cont=args.cont, incremental=args.incremental,
        update=args.update)