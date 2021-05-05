from app.tools import try_perform
from datetime import datetime
import logging
import os
import re
import threading
from time import sleep

from lxml.cssselect import CSSSelector
from more_itertools import map_reduce
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker

from app.utils.atomy import atomy_login, get_document_from_url
from app.exceptions import AtomyLoginError
from app.network.models.node import Node

class SessionManager:
    __instance = None

    @classmethod
    def create_instance(cls, username, password):
        cls.__instance = SessionManager(username, password)

    @classmethod
    def get_instance(cls):
        return cls.__instance

    def __init__(self, username, password):
        self.__username = username
        self.__password = password
        self.__create_session()

    def __create_session(self):
        with threading.Lock():
            self.__session = atomy_login(
                username=self.__username, password=self.__password, run_browser=False)

    def get_document(self, url, raw_data):
        attempts_left = 3
        while attempts_left:
            try:
                return get_document_from_url(url,
                    headers=[{'Cookie': c} for c in self.__session],
                    raw_data=raw_data)
            except AtomyLoginError:
                logger.info("Session expired. Logging in")
                self.__create_session()
                attempts_left -= 1

sel_name = lambda e: e.cssselect('td span')[1].attrib['title']
sel_rank = lambda e: e.cssselect('td span')[2].text
sel_highest_rank = lambda e: e.cssselect('td span')[3].text
sel_center = lambda e: e.cssselect('td span')[4].text
sel_country = lambda e: e.cssselect('td span')[5].text
sel_members = CSSSelector('div#dLine table')
sel_signup_date = lambda e: e.cssselect('td span')[6].text
sel_pv = lambda e: e.cssselect('td span')[7].text
sel_network_pv = lambda e: e.cssselect('td span')[8].text
TREE_URL = 'https://www.atomy.kr/v2/Home/MyAtomy/GroupTree2'
DATA_TEMPLATE = "Slevel={}&VcustNo={}&VbuCustName=0&VgjisaCode=1&VgmemberAuth=0&VglevelCnt=0&Vglevel=1&VglevelMax=1&VgregDate=1&VgcustDate=0&VgstopDate=0&VgtotSale=1&VgcumSale=0&VgcurSale=1&VgbuName=1&SDate=2021-02-23&EDate=2021-02-23&glevel=1&glevelMax=1&gbu_name=1&gjisaCode=1&greg_date=1&gtot_sale=1&gcur_sale=1"

DB_HOST = os.environ.get('DB_HOST') or 'localhost'
DB_USER = os.environ.get('DB_USER') or 'omc'
DB_PASS = os.environ.get('DB_PASSWORD') or 'omc'
DB_DB = os.environ.get('DB_DB') or 'order_master_common'
engine = create_engine(
    f"mysql+mysqldb://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_DB}?auth_plugin=mysql_native_password&charset=utf8",
    pool_size=30, max_overflow=0)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

logging.basicConfig(level=logging.INFO, force=True,
    format="%(asctime)s\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s")
logger = logging.getLogger('build_network')

def build_network(username='S5832131', password='mkk03020529!', root_id='S5832131',
    update=False, incremental=False, cont=False, active=True, threads=10):
    if not root_id:
        root_id = 'S5832131'
    tasks = []
    traversing_nodes = [node.id for node 
                        in _init_network(root_id, incremental=incremental,
                                         cont=cont, update=update, active=active)]
    logger.debug(traversing_nodes)
    logger.info("Logging in to Atomy")
    SessionManager.create_instance(username, password)
    c = 0
    initial_nodes_count = len(traversing_nodes)
    while True:
        while len([t for t in tasks if t.is_alive()]) >= threads:
            sleep(1)
        try:
            node_id = traversing_nodes[c]
            c += 1
            logger.info("%s of %s. %s tasks are running", c, len(traversing_nodes), len([t for t in tasks if t.is_alive()]))
            thread = threading.Thread(
                target=_build_page_nodes, args=(node_id, traversing_nodes, update),
                name="Thread-" + node_id)
            thread.start()
            tasks.append(thread)
        except IndexError:
            running_tasks = len([t for t in tasks if t.is_alive()])
            if running_tasks == 0:
                logger.info('No nodes left to check. Finishing')
                break
            logger.info('%s nodes checking is in progress. Waiting for completion',
                running_tasks)
            sleep(5)
        except Exception as ex:
            logger.exception(node_id)
            raise ex
    logger.info("Done. Added %s new nodes", len(traversing_nodes) - initial_nodes_count)

def _build_page_nodes(node_id, traversing_nodes, update):
    session = Session()
    for levels in [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]:
        try:
            page = SessionManager.get_instance().get_document(TREE_URL,
                raw_data=DATA_TEMPLATE.format(levels, node_id))
        except Exception as ex:
            logger.exception("Couldn't get tree page")
            raise ex
        members = sel_members(page)
        if len(members) > 0:
            logger.debug("Got %s levels. Processing", levels)
            last_level_top = max(map_reduce(
                members,
                keyfunc=lambda m: int(_get_element_style_items(m)['top'][:-2])
            ).keys())
            if update:
                # logger.info("Processing nodes %s-%s", nodes, nodes + len(members))
                _update_nodes(traversing_nodes, members, last_level_top, session)
                # nodes += len(members)
            else:
                _get_children(
                    node_id, traversing_nodes, members[0], members[1:],
                    level_distance=_get_levels_distance(members),
                    last_level_top=last_level_top, session=session
                )
            logger.debug('Committing transaction')
            session.commit()
            Session.remove()
            logger.debug('Done')
            # sleep(60)
            break
        logger.debug("Couldn't get %s levels. Decreasing", levels)

def _get_children(node_id, traversing_nodes, node_element,
    elements, level_distance, last_level_top, session):
    def get_node(node_id):
        node = session.query(Node).get(node_id)
        if node is None:
            raise ValueError(f"The node with ID {node_id} wasn't found in the DB")
        return node

    node_element_style_items = _get_element_style_items(node_element)
    node_element_top = int(node_element_style_items['top'][:-2])
    next_layer_top = node_element_top + level_distance
    next_layer_elements = [e for e in elements
                           if int(_get_element_style_items(e)['top'][:-2]) == next_layer_top]
    left = right = left_element = right_element = None
    is_left_found = False
    logger.debug("Getting node by ID %s", node_id)
    node = try_perform(lambda: get_node(node_id))
    logger.debug("Getting children for %s", node_id)
    for element in sorted(
        next_layer_elements, key=lambda e: int(_get_element_style_items(e)['left'][:-2])):
        element_id = element.attrib['id'][1:]
        logger.debug("Checking %s", element_id)
        if _is_left(node_element, element):
            logger.debug("%s is left to %s", element_id, node.id)
            if node.left_id is None:
                logger.debug("%s has no left child. Adding %s", node.id, element_id)
                left = _get_node(element, node, True, session)
                logger.debug("%s is added to DB as left child of %s", element_id, node.id)
                left_element = element
            else:
                logger.debug('%s already has left child %s', node.id, node.left_id)
            is_left_found = True
        elif _is_right(node_element, element):
            logger.debug("%s is right to %s", element_id, node.id)
            if  is_left_found:
                right = _get_node(element, node, False, session)
                logger.debug("%s is added to DB as right child of %s", element_id, node.id)
                right_element = element
    if node_element_top == last_level_top and len(elements) != 0:
        # if node.id not in page_nodes:
            traversing_nodes.append(node.id)
            node.built_tree = False
    else:
        node.built_tree = True
        if left is not None:
            _get_children(left, traversing_nodes, left_element, elements,
                level_distance=level_distance, last_level_top=last_level_top,
                session=session)
        if right is not None:
            _get_children(right, traversing_nodes, right_element, elements,
                level_distance=level_distance, last_level_top=last_level_top,
                session=session)

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

def _init_network(root_node_id, incremental=False, cont=False, update=False, active=True):
    _logger = logging.getLogger("_init_network")
    session = Session()
    root_node = session.query(Node).get(root_node_id)
    if not root_node:
        if session.query(Node).count() == 0:
            _logger.info("The network doesn't yet exist. Starting with %s", root_node_id)
            root_node = Node(id=root_node_id)
            session.add(root_node)
            session.flush()
        else:
            raise Exception(f'No node {root_node_id} is in tree')
    if root_node.parent_id:
        result = _init_network_subtree(root_node, incremental=incremental,
                                     cont=cont, update=update, active=active,
                                     session=session)
    else:
        result = _init_network_full(root_node, incremental=incremental, cont=cont,
                                  update=update, active=active,
                                  session=session)
    Session.remove()
    return result

def _init_network_subtree(root_node, incremental=False, cont=False, update=False,
                          active=True, session=None):
    _logger = logging.getLogger('_init_network_subtree')
    if incremental:
        _logger.info("Resetting leafs progress")
        session.execute('''
            UPDATE network_nodes
            SET built_tree = 0 
            WHERE id IN (
                WITH RECURSIVE cte(id) AS (
                    SELECT id FROM network_nodes WHERE id = :id
                    UNION
                    SELECT n.id FROM network_nodes AS n JOIN cte ON n.parent_id = cte.id
                ) SELECT id FROM cte
            ) AND right_id IS NULL
        ''', {'id': root_node.id})
    _logger.info("Getting leafs to crawl")
    traversing_nodes_query = session.query(Node)
    cte = session.query(Node.id).filter_by(id=root_node.id).cte(recursive=True)
    ids = cte.union(session.query(aliased(Node).id).filter_by(parent_id=cte.c.id))
    if incremental:
        traversing_nodes_query = traversing_nodes_query.filter_by(right_id=None)
        if active:
            traversing_nodes_query = traversing_nodes_query.filter(Node.pv > 10)
        traversing_nodes_query = traversing_nodes_query.join(ids, Node.id == ids.c.id)
    elif cont:
        traversing_nodes_query = traversing_nodes_query.\
            filter_by(built_tree=False).join(ids, Node.id == ids.c.id)
    elif update:
        _logger.info("There are %s nodes to update", session.query(ids).count())
        traversing_nodes_query = session.query(Node).filter_by(id=root_node.id)
    else:
        raise Exception("No mode is defined")
            
    traversing_nodes = traversing_nodes_query.all()
    _logger.info("Done")
    return traversing_nodes

def _init_network_full(root_node, incremental=False, cont=False, update=False,
                       active=True, session=None):
    _logger = logging.getLogger('_init_network_full')
    if incremental:
        _logger.info("Resetting leafs progress")
        session.execute('''
            UPDATE network_nodes
            SET built_tree = 0 
            WHERE right_id IS NULL
        ''')
    _logger.info("Getting leafs to crawl")
    traversing_nodes_query = session.query(Node)
    if incremental:
        traversing_nodes_query = traversing_nodes_query.\
            filter_by(right_id=None)
        if active:
            traversing_nodes_query = traversing_nodes_query.filter(Node.pv > 10)
    elif cont:
        traversing_nodes_query = traversing_nodes_query.filter_by(built_tree=False)
        if active:
            traversing_nodes_query = traversing_nodes_query.filter(Node.pv > 10)
    elif update:
        traversing_nodes_query = session.query(Node).filter_by(id=root_node.id)
            
    traversing_nodes = traversing_nodes_query.all()
    _logger.info("Done")
    return traversing_nodes

def _get_node(element, parent, is_left, session):
    logger = logging.getLogger('_get_node')
    id = element.attrib['id'][1:]
    try:
        signup_date = datetime.strptime(sel_signup_date(element), '%y-%m-%d')
    except Exception as ex:
        logger.error("In %s the error has happened", id)
        raise ex
    node = Node(
        id=id, parent_id=parent.id,
        name=sel_name(element),
        rank=sel_rank(element),
        highest_rank=sel_highest_rank(element),
        center=sel_center(element),
        country=sel_country(element),
        signup_date=signup_date,
        pv=int(re.search('\\d+', sel_pv(element)).group()),
        network_pv=int(re.search('\\d+', sel_network_pv(element)).group())
    )
    logger.debug('Adding node %s', id)
    if is_left:
        parent.left_id = id
    else:
        parent.right_id = id    
    session.commit()
    session.add(node)
    try:
        session.flush()
    except UnicodeEncodeError as ex:
        logger.error("Couldn't add object %s", node.to_dict())
        logger.error(ex)
        raise ex
    except IntegrityError as ex:
        session.rollback()
        node = session.query(Node).get(id)
        if node is None:
            raise ex
    except Exception as ex:
        logger.error(ex)
        raise ex

    return node

def _is_left(parent_element, child_element):
    v_lines = _get_vertical_lines(parent_element, child_element)
    if v_lines is None:
        return False
    horizontal_line = _get_element_horizontal_line(parent_element)
    if horizontal_line is not None:
        return v_lines['child']['top'] == v_lines['parent']['bottom'] \
           and v_lines['child']['left'] == \
               int(_get_element_style_items(horizontal_line)['left'][:-2])
    else:
        return v_lines['child']['top'] == v_lines['parent']['bottom'] \
           and v_lines['child']['left'] == v_lines['parent']['left']

def _is_right(parent_element, child_element):
    v_lines = _get_vertical_lines(parent_element, child_element)
    if v_lines is None:
        return False
    horizontal_line = _get_element_horizontal_line(parent_element)
    if horizontal_line is not None:
        h_line_style_items = _get_element_style_items(horizontal_line)
        return v_lines['child']['top'] == v_lines['parent']['bottom'] \
           and v_lines['child']['left'] == \
               int(h_line_style_items['left'][:-2]) + int(h_line_style_items['width'][:-2])
    else:
        return False

def _get_vertical_lines(parent_element, child_element):
    parent_vertical_line = parent_element.getnext()
    if parent_vertical_line is not None and \
       int(_get_element_style_items(parent_vertical_line)['top'][:-2]) < \
       int(_get_element_style_items(parent_element)['top'][:-2]):
        parent_vertical_line = parent_vertical_line.getnext()
        if parent_vertical_line is None or parent_vertical_line.tag != 'img':
            return None
    parent_vertical_line_style_items = _get_element_style_items(parent_vertical_line)
    child_vertical_line = child_element.getnext()
    return {
        'parent':{
            'bottom': int(parent_vertical_line_style_items['top'][:-2]) + \
                      int(parent_vertical_line_style_items['height'][:-2]) - 1,
            'left': int(parent_vertical_line_style_items['left'][:-2])
        },
        'child': {
            'top': int(_get_element_style_items(child_vertical_line)['top'][:-2]),
            'left': int(_get_element_style_items(child_vertical_line)['left'][:-2])
        }
    }

def _get_element_horizontal_line(element):
    next_element = element.getnext()
    while True:
        if next_element.tag == 'img' and next_element.attrib['src'].endswith('line.gif'):
            return next_element
        elif next_element.tag == 'table':
            return None
        next_element = next_element.getnext()
    
def _update_nodes(traversing_nodes, elements, last_level_top, session):
    # logger = logging.getLogger('_update_nodes')
    for element in elements:
        # node = [n for n in nodes if n.id == element.attrib['id'][1:]][0]
        node = session.query(Node).get(element.attrib['id'][1:])
        if node:
            node.rank = sel_rank(element)
            node.highest_rank = sel_highest_rank(element)
            node.pv = re.search('\\d+', sel_pv(element)).group()
            node.network_pv = re.search('\\d+', sel_network_pv(element)).group()
            if int(_get_element_style_items(element)['top'][:-2]) == last_level_top \
               and len(elements) > 1:
                traversing_nodes.append(node.id)

if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description="Build network")
    group = arg_parser.add_mutually_exclusive_group()
    arg_parser.add_argument('--root', metavar='ROOT_ID', help="ID of the tree or subtree root")
    group.add_argument('--update', help='Update data of existing nodes', action='store_true')
    group.add_argument('--incremental', help='Build trees from all leaves',
                    action='store_true')
    group.add_argument('--continue', dest='cont',
                    help='Continue tree building after being interrupted', action='store_true')
    active = arg_parser.add_mutually_exclusive_group()
    active.add_argument('--active', help="Build only active branches", default=True, action="store_true")
    active.add_argument('--all', help="Build all branches", dest='active', default=False, action="store_false")
    arg_parser.add_argument('-v', '--verbose', action='count', help='Increase verbosity')
    arg_parser.add_argument('--threads', help="Number of threads to run", type=int, default=10)

    args = arg_parser.parse_args()
    args.incremental = not (args.update or args.cont or args.root)
    if args.verbose == 1:
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info('Building tree with following arguments: %s', args)

    build_network(
        root_id=args.root, cont=args.cont, incremental=args.incremental,
        update=args.update, active=args.active, threads=args.threads)
