from enum import Enum
from calendar import monthrange
import cProfile
from datetime import datetime
import utils.logging as logging
import os, os.path
import re
import threading
from time import sleep

from lxml.cssselect import CSSSelector
from more_itertools import map_reduce
from neomodel import db, config

from exceptions import AtomyLoginError
from utils import get_document_from_url
from utils.atomy import atomy_login

from model import AtomyPerson

class SessionManager:
    __instance = None

    @classmethod
    def create_instance(cls, username, password):
        cls.__instance = SessionManager(username, password)

    @classmethod
    def get_instance(cls) -> 'SessionManager':
        if cls.__instance is None:
            raise AtomyLoginError()
        return cls.__instance

    def __init__(self, username, password):
        self.__username = username
        self.__password = password
        self.__create_session()

    def __create_session(self):
        with threading.Lock():
            self.__session = atomy_login(
                username=self.__username, password=self.__password)

    def get_document(self, url, raw_data):
        attempts_left = 3
        while attempts_left:
            try:
                return get_document_from_url(url,
                    headers=[{'Cookie': c} for c in self.__session], 
                    raw_data=raw_data)
            except AtomyLoginError:
                logger = logging.getLogger('SessionManager.get_document()')
                logger.info("Session expired. Logging in")
                self.__create_session()
                attempts_left -= 1

class ChildType(Enum):
    LEFT = 0
    RIGHT = 1

# Build selection range
today = datetime.today()
month_range = monthrange(today.year, today.month)
start_date = today.strftime('%Y-%m-01' if today.day < 16 else '%Y-%m-16')
end_date = today.strftime(f'%Y-%m-{15 if today.day < 16 else month_range[1]:02d}')
######
sel_members = CSSSelector('div#dLine table')
sel_name = lambda e: e[0][0][1].attrib.get('title')
sel_rank = lambda e: e[0][0][2].text if len(e[0][0]) > 2 else e[0][0][1][0].text
sel_highest_rank = lambda e: e[0][0][3].text if len(e[0][0]) > 2 else e[0][0][1][1].text
sel_center = lambda e: e[0][0][4].text if len(e[0][0]) > 2 else e[0][0][1][2].text
sel_country = lambda e: e[0][0][5].text if len(e[0][0]) > 2 else e[0][0][1][3].text
sel_signup_date = lambda e: e[0][0][6].text if len(e[0][0]) > 2 else e[0][0][1][4].text
sel_pv = lambda e: e[0][0][7].text if len(e[0][0]) > 2 else e[0][0][1][5].text
sel_total_pv = lambda e: e[0][0][8].text if len(e[0][0]) > 2 else e[0][0][1][6].text
sel_network_pv = lambda e: e[0][0][9].text if len(e[0][0]) > 2 else e[0][0][1][7].text
TREE_URL = 'https://www.atomy.kr/v2/Home/MyAtomy/GroupTree2'
DATA_TEMPLATE = "Slevel={}&VcustNo={}&VbuCustName=0&VgjisaCode=1&VgmemberAuth=0&VglevelCnt=0&Vglevel=1&VglevelMax=1&VgregDate=1&VgcustDate=0&VgstopDate=0&VgtotSale=1&VgcumSale=1&VgcurSale=1&VgbuName=1&SDate={}&EDate={}&glevel=1&glevelMax=1&gbu_name=1&gjisaCode=1&greg_date=1&gtot_sale=1&gcur_sale=1"

############# Neo4j connection ###################
config.DATABASE_URL = 'bolt://neo4j:1@localhost:7687'



##################################################

logging.basicConfig(level=logging.INFO, force=True,
    format="%(asctime)s\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s")
lock = threading.Lock()

def build_network(user, password, root_id='S5832131', cont=False, active=True, 
                  threads=10, profile=False, **_kwargs):
    logger = logging.getLogger('build_network')
    if not root_id:
        root_id = 'S5832131'
    if profile and not os.path.exists('profiles'):
        os.mkdir('profiles')

    tasks = []
    traversing_nodes_set = _init_network(root_id, cont=cont, active=active)
    traversing_nodes_list = sorted(list(traversing_nodes_set), key=lambda i: i.replace('S', '0'))
    logger.debug(traversing_nodes_list)
    logger.info("Logging in to Atomy")
    SessionManager.create_instance(user, password)
    c = 0
    initial_nodes_count = len(traversing_nodes_list)
    while True:
        while len([t for t in tasks if t.is_alive()]) >= threads:
            sleep(1)
        try:
            with lock:
                while traversing_nodes_list[c] not in traversing_nodes_set:
                    logger.debug("Node %s was already crawled. Skipping...", traversing_nodes_list[c])
                    c += 1
            node_id = traversing_nodes_list[c]
            c += 1
            logger.info("Processing %s (%s of %s). %s tasks are running",
                        node_id, c, len(traversing_nodes_list),
                        len([t for t in tasks if t.is_alive()]))
            if profile:
                thread = threading.Thread(
                    target=_profile_thread,
                    args=("Thread-" + node_id, _build_page_nodes, node_id, traversing_nodes_set, traversing_nodes_list),
                    name="Thread-" + node_id)
            else:
                thread = threading.Thread(
                    target=_build_page_nodes, args=(node_id, traversing_nodes_set, traversing_nodes_list),
                    name="Thread-" + node_id)

            thread.start()
            # thread.join()
            # exit(0)
            tasks.append(thread)
        except IndexError:
            running_tasks = len([t for t in tasks if t.is_alive()])
            if running_tasks == 0:
                logger.info('No nodes left to check. Finishing')
                break
            logger.info('%s nodes checking is in progress. Waiting for completion',
                running_tasks)
            sleep(5)
        except KeyboardInterrupt:
            logger.info("Ctrl+C was pressed. Shutting down (running threads will be completed)...")
            break
        except Exception as ex:
            logger.exception(node_id)
            raise ex
    logger.info("Done. Added %s new nodes", len(traversing_nodes_list) - initial_nodes_count)
    logger.info("Updating network PV for each node")
    result, _ = db.cypher_query('''
        MATCH (n:AtomyPerson) WHERE ID(n) = 0
        MATCH (n)<-[:PARENT*0..]-(n1)-[:LEFT_CHILD]->()
        WITH n1
        ORDER BY n1.atomy_id_normalized DESC
        CALL {
            WITH n1
            MATCH (l)<-[:LEFT_CHILD]-(n1)
            OPTIONAL MATCH (n1)-[:RIGHT_CHILD]->(r)
            WITH 
                n1, l.network_pv AS l_pv, 
                CASE r WHEN NULL THEN 0 ELSE r.network_pv END AS r_pv,
                CASE n1.total_pv WHEN NULL THEN 0 ELSE n1.total_pv END AS t_pv
            SET n1.network_pv = l_pv + r_pv + t_pv
            RETURN n1.atomy_id AS id, n1.total_pv AS t_pv, n1.network_pv AS n_pv, l_pv, r_pv
        }
        RETURN COUNT(*)
    ''')
    logger.info("Update result: %s", result)

def _profile_thread(thread_name, target, *args):
    profiler = cProfile.Profile()
    profiler.enable()
    target(*args)
    profiler.disable()
    profiler.dump_stats("profiles/profile-" + thread_name + '-' + datetime.now().strftime('%Y%m%d_%H%M%S'))

def _build_page_nodes(node_id, traversing_nodes_set, traversing_nodes_list):
    logger = logging.getLogger('_build_page_nodes()')
    for levels in [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]:
        try:
            page = SessionManager.get_instance().get_document(TREE_URL,
                raw_data=DATA_TEMPLATE.format(levels, node_id, start_date, end_date))
        except Exception as ex:
            logger.exception("Couldn't get tree page")
            raise ex
        members: list = sel_members(page) # type: ignore
        if len(members) > 0:
            logger.debug("Got %s levels. Processing", levels)
            logger.debug("%s elements on the page to be processed", len(members))
            elements = [
                {
                    'id': e.attrib['id'][1:],
                    'element': e,
                    'style_items': _get_element_style_items(e)
                } for e in members]
            last_level_top = max(map_reduce(
                elements,
                keyfunc=lambda m: int(m['style_items']['top'][:-2])
            ).keys())
            # Update or create root node
            if node_id == args.root_id:
                _get_node(members[0], None, False, logger)
            _get_children(
                node_id, traversing_nodes_set, traversing_nodes_list, elements[0], elements[1:],
                level_distance=_get_levels_distance(elements),
                last_level_top=last_level_top, logger=logger
            )
            logger.debug('Done')
            # sleep(60)
            break
        logger.debug("Couldn't get %s levels. Decreasing", levels)
    logger.debug("Done building node %s", node_id)

def get_child_id(parent_id, child_type):
    result, _ = db.cypher_query(f'''
        MATCH (p:AtomyPerson {{atomy_id: '{parent_id}'}})-[:{child_type.name}_CHILD]->(c:AtomyPerson)
        RETURN c.atomy_id
    ''')
    return result[0][0] if len(result) > 0 else None

def _get_children(node_id, traversing_nodes_set: set, traversing_nodes_list: list, node_element,
    elements, level_distance, last_level_top, logger):

    node_element_style_items = node_element['style_items']
    node_element_top = int(node_element_style_items['top'][:-2])
    next_layer_top = node_element_top + level_distance
    next_layer_elements = [e for e in elements
                           if int(e['style_items']['top'][:-2]) == next_layer_top]
    left = right = left_element = right_element = None
    logger.fine("Getting children for %s", node_id)
    for element in sorted(
        next_layer_elements, key=lambda e: int(e['style_items']['left'][:-2])):
        if left is not None and right is not None:
            # Both children are found. Nothing more to do
            break
        element_id = element['id']
        logger.debug("Checking %s", element_id)
        if element_id.replace('S', '0') < node_id.replace('S', '0'):
            continue
        if _is_left(node_element['element'], element['element']):
            logger.debug("%s is left to %s", element_id, node_id)
            left_child_id = get_child_id(node_id, ChildType.LEFT)
            if left_child_id is None:
                logger.debug("%s has no left child. Adding %s", node_id, element_id)
                left = _get_node(element=element['element'], parent_id=node_id, is_left=True, logger=logger)
                logger.debug("%s is added to DB as left child of %s", element_id, node_id)
                left_element = element
            else:
                if left_child_id != element_id:
                    logger.warning(
                        "%s has %s as a left child. Will be overwritten with %s.",
                        node_id, left_child_id, element_id)
                else:
                    logger.debug(
                        '%s already has %s as a left child. Updating data...',
                        node_id, element_id)
                left = _get_node(element=element['element'], parent_id=node_id, is_left=True, logger=logger)
                left_element = element
        elif _is_right(node_element['element'], element['element']):
            logger.debug("%s is right to %s", element_id, node_id)
            right_child_id = get_child_id(node_id, ChildType.RIGHT)
            if right_child_id is None:
                logger.debug("%s has no right child. Adding %s", node_id, element_id)
                if  left is not None:
                    right = _get_node(element=element['element'], parent_id=node_id, is_left=False, logger=logger)
                    logger.debug("%s is added to DB as right child of %s", element_id, node_id)
                    right_element = element
                else:
                    logger.warning("No left child was found for %s before. I don't know what to do. Skipping %s",
                                   node_id, element_id)
            else:
                if right_child_id != element_id:
                    logger.warning(
                        "%s has %s as a right child. Will be overwritten with %s.",
                        node_id, right_child_id, element_id)
                else:
                    logger.debug(
                        '%s already has %s as a right child. Updating data...',
                        node_id, element_id)
                right = _get_node(element=element['element'], parent_id=node_id, is_left=False, logger=logger)
                right_element = element
        elif left is not None:
            # left is already found and next must be right
            # if next one isn't right then right isn't there at all
            break        
    if node_element_top == last_level_top and len(elements) != 0:
        # Means the element is the last one in row but not a single one on the page
        # Therefore it has to be crowled further until single element on the page appears
        if node_id not in traversing_nodes_set:
            traversing_nodes_set.add(node_id)
            traversing_nodes_list.append(node_id)
    else:
        # Here node is set as built
        # Dynamic properties are updated either set during processing this node
        # as child one or for root node at the very beginning of the process
        db.cypher_query('''
            MATCH (node:AtomyPerson {atomy_id: $atomy_id}) 
            SET
                node.built_tree = true
            ''', params={
                'atomy_id': node_id
            })
        if left is not None:
            _get_children(left.atomy_id, traversing_nodes_set, traversing_nodes_list,
                left_element, elements, level_distance=level_distance, last_level_top=last_level_top,
                logger=logger)
        if right is not None:
            _get_children(right.atomy_id, traversing_nodes_set, traversing_nodes_list,
                right_element, elements, level_distance=level_distance, last_level_top=last_level_top,
                logger=logger)
        with lock:
            logger.debug("%s is done. Removing from the crawling set", node_id)
            traversing_nodes_set.discard(node_id)

def _get_element_style_items(element) -> dict[str, str]:
    style_items: list[str] = element.attrib['style'].split(';') \
        if element.attrib.get('style') else []
    dict_style_items = {e.split(':')[0].strip(): e.split(':')[1].strip()
                        for e in style_items
                        if ':' in e}
    return dict_style_items

def _get_element_left(element) -> int:
    style_items = _get_element_style_items(element)
    if len(style_items) > 0:
        return int(style_items['left'][:-2]) 
    raise Exception("The element has no style attributes and no position")

def _get_element_top(element):
    style_items = _get_element_style_items(element)
    if len(style_items) > 0:
        return int(style_items['top'][:-2]) 
    raise Exception("The element has no style attributes and no position")

def _get_levels_distance(members):
    if len(members) <= 1:
        return 0
    first_level = int(members[0]['style_items']['top'][:-2])
    second_level = int(members[1]['style_items']['top'][:-2])
    return second_level - first_level

def _init_network(root_node_id, cont=False, active=True):
    logger = logging.getLogger("_init_network")
    neo4j_root = AtomyPerson.nodes.get_or_none(atomy_id=root_node_id, lazy=False)
    if neo4j_root is None:
        neo4j_root = AtomyPerson(atomy_id=root_node_id).save()

    logger.info('Getting leafs to crawl')
    if not cont:
        logger.debug("Resetting 'built_tree' attribute")
        db.cypher_query('MATCH (n:AtomyPerson {built_tree: true}) SET n.built_tree = false')
    if cont or active:
        _filter = ''
        if active:
            _filter += ' AND leaf.pv > 10'
        if cont:
            _filter += ' AND NOT leaf.built_tree'
        result, _ = db.cypher_query(f'''
            MATCH (root:AtomyPerson {{atomy_id:$root_id}})<-[:PARENT*0..]-(leaf:AtomyPerson)
            WHERE {_filter[5:]}
            RETURN leaf.atomy_id
        ''', params={'root_id': root_node_id})
        leafs = {item[0] for item in result}
    else:
        leafs = {root_node_id}
    logger.info('Done')
    return leafs

def _get_node(element, parent_id, is_left, logger: logging.Logger):
    atomy_id = element.attrib['id'][1:]
    try:
        signup_date_str = sel_signup_date(element)
        signup_date = datetime(int(signup_date_str[:2]), 
                               int(signup_date_str[3:5]), 
                               int(signup_date_str[6:8]))
        pv = int(re.search('\\d+', sel_pv(element)).group()) # type: ignore
        total_pv = int(re.search('\\d+', sel_total_pv(element)).group()) # type: ignore
        network_pv = int(re.search('\\d+', sel_network_pv(element)).group()) # type: ignore
    except Exception as ex:
        logger.exception("_get_node(): In %s the error has happened", atomy_id)
        raise ex
    if parent_id is None:
        node = _save_root_node(atomy_id, element, signup_date, pv, total_pv, 
                               network_pv)
    else:
        node = _save_child_node(atomy_id, parent_id, element, is_left, 
                                signup_date, pv, total_pv, network_pv)
    logger.debug('Saved node %s: {rank: %s, pv: %s, total_pv: %s, network_pv: %s}',
                    atomy_id, node.rank, node.pv, node.total_pv, node.network_pv)
    return node
        
def _save_root_node(atomy_id: str, element, signup_date: datetime, pv: int, 
                    total_pv: int, network_pv: int) -> AtomyPerson:
    result, _ = db.cypher_query('''
        MERGE (node:AtomyPerson {atomy_id: $atomy_id})
        ON CREATE SET
                node.atomy_id_normalized = REPLACE($atomy_id, 'S', '0'),
                node.name = $name,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.center = $center,
                node.country = $country,
                node.signup_date = $signup_date,
                node.pv = $pv,
                node.total_pv = $total_pv,
                node.network_pv = $network_pv,
                node.when_updated = $now
        ON MATCH SET
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.pv = $pv,
                node.total_pv = $total_pv,
                node.network_pv = $network_pv,
                node.when_updated = $now
        RETURN node
    ''', params={
        'atomy_id': atomy_id,
        'name': sel_name(element),
        'rank': sel_rank(element),
        'highest_rank': sel_highest_rank(element),
        'center': sel_center(element),
        'country': sel_country(element),
        'signup_date': signup_date,
        'pv': pv,
        'total_pv': total_pv,
        'network_pv': network_pv,
        'now': datetime.now()
    })
    return AtomyPerson.inflate(result[0][0])

def _save_child_node(atomy_id: str, parent_id: str, element, is_left: bool, 
                     signup_date: datetime, pv: int, total_pv: int, 
                     network_pv: int) -> AtomyPerson:
    result, _ = db.cypher_query(f'''
        MATCH (parent:AtomyPerson {{atomy_id: $parent_id}})
        MERGE (node:AtomyPerson {{atomy_id: $atomy_id}})
        ON CREATE SET
                node.atomy_id_normalized = REPLACE($atomy_id, 'S', '0'),
                node.name = $name,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.center = $center,
                node.country = $country,
                node.signup_date = $signup_date,
                node.pv = $pv,
                node.total_pv = $total_pv,
                node.network_pv = $network_pv,
                node.when_updated = $now
        ON MATCH SET
                node.name = $name,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.center = $center,
                node.country = $country,
                node.pv = $pv,
                node.total_pv = $total_pv,
                node.network_pv = $network_pv,
                node.when_updated = $now
        MERGE (node)-[:PARENT]->(parent)
        MERGE (parent)-[:{"LEFT" if is_left else "RIGHT"}_CHILD]->(node)
        RETURN node
    ''', params={
        'atomy_id': atomy_id,
        'parent_id': parent_id,
        'name': sel_name(element),
        'rank': sel_rank(element),
        'highest_rank': sel_highest_rank(element),
        'center': sel_center(element),
        'country': sel_country(element),
        'signup_date': signup_date,
        'pv': pv,
        'total_pv': total_pv,
        'network_pv': network_pv,
        'now': datetime.now()
    })
    return AtomyPerson.inflate(result[0][0])

def _is_left(parent_element, child_element):
    v_lines = _get_vertical_lines(parent_element, child_element)
    if v_lines is None:
        return False
    horizontal_line = _get_element_horizontal_line(parent_element)
    if horizontal_line is not None:
        return v_lines['child']['top'] == v_lines['parent']['bottom'] \
           and v_lines['child']['left'] == _get_element_left(horizontal_line)
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
       _get_element_top(parent_vertical_line) < _get_element_top(parent_element):
        parent_vertical_line = parent_vertical_line.getnext()
        if parent_vertical_line is None or parent_vertical_line.tag != 'img':
            return None
    parent_vertical_line_style_items = _get_element_style_items(parent_vertical_line)
    child_vertical_line = child_element.getnext()
    return {
        'parent':{
            'bottom': _get_element_top(parent_vertical_line) + \
                      int(parent_vertical_line_style_items['height'][:-2]) - 1,
            'left': _get_element_left(parent_vertical_line)
        },
        'child': {
            'top': _get_element_top(child_vertical_line),
            'left': _get_element_left(child_vertical_line)
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

if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description="Build network")
    mode = arg_parser.add_mutually_exclusive_group()
    arg_parser.add_argument('--user', help="User name to log on to Atomy", default='S5832131')
    arg_parser.add_argument('--password', help="Password to log on to Atomy", default='mkk03020529!!')
    # mode.add_argument('--update', help='Update data of existing nodes', action='store_true')
    mode.add_argument('--root', dest='root_id', metavar='ROOT_ID', help="ID of the tree or subtree root for full network scan")
    mode.add_argument('--continue', dest='cont',
                    help='Continue tree building after being interrupted', action='store_true')
    arg_parser.add_argument('--active', help="Build only active branches", default=False, action="store_true")
    arg_parser.add_argument('-v', '--verbose', action='count', help='Increase verbosity')
    arg_parser.add_argument('--threads', help="Number of threads to run", type=int, default=10)
    arg_parser.add_argument('--profile', help="Profile threads", default=False, action="store_true")

    if os.environ.get('TERM_PROGRAM') == 'vscode':
        # Means we run in VSCode debugger
        args = arg_parser.parse_args(['--user', 'S5832131', '--password', 'mkk03020529!!', '--threads', '1', '--root', '35467900', '-v'])
        # args = arg_parser.parse_args(['--user', 'S0004669', '--password', 'a121212**', '--update', '--verbose', '--threads', '1'])
    else: 
        # Production run
        args = arg_parser.parse_args()
    if args.verbose == 1:
        logging.getLogger().setLevel(logging.FINE)
    elif args.verbose == 2:
        logging.getLogger().setLevel(logging.DEBUG)


    logging.info('Building tree with following arguments: %s', args)
    build_network(**args.__dict__)
    logging.info("Job is done")
