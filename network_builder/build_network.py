from enum import Enum
from calendar import monthrange
import cProfile
from datetime import datetime
import logging
import os, os.path
import re
import threading
from time import sleep

from lxml.cssselect import CSSSelector
from more_itertools import map_reduce
from neomodel import db, config

from utils.atomy import atomy_login, get_document_from_url
from exceptions import AtomyLoginError
from model import AtomyPerson

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
        logger = logging.getLogger('SessionManager.get_document()')
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

class ChildType(Enum):
    LEFT = 0
    RIGHT = 1

# Build selection range
today = datetime.today()
month_range = monthrange(today.year, today.month)
start_date = today.strftime(f'%Y-%m-01')
end_date = today.strftime(f'%Y-%m-{month_range[1]:02d}')
######
sel_name = lambda e: e.cssselect('td span')[1].attrib.get('title')
sel_rank = lambda e: e.cssselect('td span')[2].text
sel_highest_rank = lambda e: e.cssselect('td span')[3].text
sel_center = lambda e: e.cssselect('td span')[4].text
sel_country = lambda e: e.cssselect('td span')[5].text
sel_members = CSSSelector('div#dLine table')
sel_signup_date = lambda e: e.cssselect('td span')[6].text
sel_pv = lambda e: e.cssselect('td span')[7].text
sel_network_pv = lambda e: e.cssselect('td span')[9].text
TREE_URL = 'https://www.atomy.kr/v2/Home/MyAtomy/GroupTree2'
DATA_TEMPLATE = "Slevel={}&VcustNo={}&VbuCustName=0&VgjisaCode=1&VgmemberAuth=0&VglevelCnt=0&Vglevel=1&VglevelMax=1&VgregDate=1&VgcustDate=0&VgstopDate=0&VgtotSale=1&VgcumSale=1&VgcurSale=1&VgbuName=1&SDate={}&EDate={}&glevel=1&glevelMax=1&gbu_name=1&gjisaCode=1&greg_date=1&gtot_sale=1&gcur_sale=1"

############# Neo4j connection ###################
config.DATABASE_URL = 'bolt://neo4j:1@localhost:7687'



##################################################

logging.basicConfig(level=logging.INFO, force=True,
    format="%(asctime)s\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s")
lock = threading.Lock()

def build_network(user, password, root_id='S5832131',
    cont=False, active=True, threads=10, profile=False, **kwargs):
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
        except Exception as ex:
            logger.exception(node_id)
            raise ex
    logger.info("Done. Added %s new nodes", len(traversing_nodes_list) - initial_nodes_count)

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
        members = sel_members(page)
        if len(members) > 0:
            logger.debug("Got %s levels. Processing", levels)
            logger.info("%s elements on the page to be processed", len(members))
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
            _get_children(
                node_id, traversing_nodes_set, traversing_nodes_list, elements[0], elements[1:],
                level_distance=_get_levels_distance(elements),
                last_level_top=last_level_top
            )
            logger.debug('Done')
            # sleep(60)
            break
        logger.debug("Couldn't get %s levels. Decreasing", levels)
    logger.info("Done building node %s", node_id)

def get_child_id(parent_id, child_type):
    result, _ = db.cypher_query(f'''
        MATCH (p:AtomyPerson {{atomy_id: '{parent_id}'}})-[:{child_type.name}_CHILD]->(c:AtomyPerson)
        RETURN c.atomy_id
    ''')
    return result[0][0] if len(result) > 0 else None

def _get_children(node_id, traversing_nodes_set: set, traversing_nodes_list: list, node_element,
    elements, level_distance, last_level_top):
    # def get_node(node_id):
    #     result, _ = db.cypher_query('''
    #         MATCH (node:AtomyPerson {atomy_id: $atomy_id})
    #         RETURN node
    #     ''', params={'atomy_id': node_id})
    #     return AtomyPerson.inflate(result[0][0])

    logger = logging.getLogger('_get_children()')
    node_element_style_items = node_element['style_items']
    node_element_top = int(node_element_style_items['top'][:-2])
    next_layer_top = node_element_top + level_distance
    next_layer_elements = [e for e in elements
                           if int(e['style_items']['top'][:-2]) == next_layer_top]
    left = right = left_element = right_element = None
    is_left_found = False
    logger.debug("Getting node by ID %s", node_id)
    # node = try_perform(lambda: get_node(node_id))
    logger.debug("Getting children for %s", node_id)
    for element in sorted(
        next_layer_elements, key=lambda e: int(e['style_items']['left'][:-2])):
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
            elif left_child_id == element_id:
                logger.debug('%s already has %s as a left child. Updating data...', node_id, element_id)
                left = _get_node(element=element['element'], parent_id=node_id, is_left=True, logger=logger)
                left_element = element
            else:
                logger.error("%s has %s as a left child and I don't know what to do with %s. Skipping %s...",
                             node_id, left_child_id, element_id, element_id)
                continue
            is_left_found = True
        elif _is_right(node_element['element'], element['element']):
            logger.debug("%s is right to %s", element_id, node_id)
            right_child_id = get_child_id(node_id, ChildType.RIGHT)
            if right_child_id is None:
                logger.debug("%s has no right child. Adding %s", node_id, element_id)
                if  is_left_found:
                    right = _get_node(element=element['element'], parent_id=node_id, is_left=False, logger=logger)
                    logger.debug("%s is added to DB as right child of %s", element_id, node_id)
                    right_element = element
                else:
                    logger.warning("No left child was found for %s before. I don't know what to do. Skipping %s",
                                   node_id, element_id)
                    continue
            elif right_child_id == element_id:
                logger.debug('%s already has %s as a right child. Updating data...', node_id, element_id)
                right = _get_node(element=element['element'], parent_id=node_id, is_left=False, logger=logger)
                right_element = element
            else:
                logger.error("%s has %s as a right child and I don't know what to do with %s. Skipping %s...",
                             node_id, right_child_id, element_id, element_id)
                continue
                
    if node_element_top == last_level_top and len(elements) != 0:
        # Means the element is the last one in row but not a single one on the page
        # Therefore it has to be crowled further until single element on the page appears
        if node_id not in traversing_nodes_set:
            traversing_nodes_set.add(node_id)
            traversing_nodes_list.append(node_id)
        # node.built_tree = False
    else:
        # Here node is set as built and dynamic properties are updated
        db.cypher_query('''
            MATCH (node:AtomyPerson {atomy_id: $atomy_id}) 
            SET
                node.built_tree = true,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.pv = $pv,
                node.network_pv = $network_pv
            ''', params={
                'atomy_id': node_id,
                'rank': sel_rank(node_element['element']),
                'highest_rank': sel_highest_rank(node_element['element']),
                'pv': int(re.search('\\d+', sel_pv(node_element['element'])).group()),
                'network_pv': int(re.search('\\d+', sel_network_pv(node_element['element'])).group())
            })
        if left is not None:
            _get_children(left.atomy_id, traversing_nodes_set, traversing_nodes_list,
                left_element, elements, level_distance=level_distance, last_level_top=last_level_top)
        if right is not None:
            _get_children(right.atomy_id, traversing_nodes_set, traversing_nodes_list,
                right_element, elements, level_distance=level_distance, last_level_top=last_level_top)
        with lock:
            logger.debug("%s is done. Removing from the crawling set", node_id)
            traversing_nodes_set.discard(node_id)

def _get_element_style_items(element):
    style_items = element.attrib['style'].split(';')
    dict_style_items = {e.split(':')[0].strip(): e.split(':')[1].strip()
                        for e in style_items
                        if ':' in e}
    return dict_style_items

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
        filter = ''
        if active:
            filter += ' AND leaf.pv > 10'
        if cont:
            filter += ' AND NOT leaf.built_tree'
        result, _ = db.cypher_query(f'''
            MATCH (root:AtomyPerson {{atomy_id:$root_id}})<-[:PARENT*0..]-(leaf:AtomyPerson)
            WHERE {filter[5:]}
            RETURN leaf.atomy_id
        ''', params={'root_id': root_node_id})
        leafs = {item[0] for item in result}
    else:
        leafs = {root_node_id}
    logger.info('Done')
    return leafs

def _get_node(element, parent_id, is_left, logger):
    atomy_id = element.attrib['id'][1:]
    try:
        signup_date = datetime.strptime(sel_signup_date(element), '%y-%m-%d')
    except Exception as ex:
        logger.exception("_get_node(): In %s the error has happened", atomy_id)
        raise ex
    result, _ = db.cypher_query(f'''
        MATCH (parent:AtomyPerson {{atomy_id: $parent_id}})
        MERGE (node:AtomyPerson {{atomy_id: $atomy_id}})
        ON CREATE SET
                node.name = $name,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.center = $center,
                node.country = $country,
                node.signup_date = $signup_date,
                node.pv = $pv,
                node.network_pv = $network_pv
        ON MATCH SET
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.pv = $pv,
                node.network_pv = $network_pv
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
        'pv': int(re.search('\\d+', sel_pv(element)).group()),
        'network_pv': int(re.search('\\d+', sel_network_pv(element)).group())
    })
    # If logging is needed, logger should be passed, not created here 
    # logger.debug('Adding node %s', atomy_id)

    return AtomyPerson.inflate(result[0][0])

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

    if os.environ.get('TERM_PROGRAM'): 
        # Means we run in VSCode debugger
        args = arg_parser.parse_args(['--user', 'S0004669', '--password', 'a121212**', '--continue', '--threads', '1', '--verbose'])
        # args = arg_parser.parse_args(['--user', 'S0004669', '--password', 'a121212**', '--update', '--verbose', '--threads', '1'])
        # args = arg_parser.parse_args(['--continue', '--all', '--verbose', '--threads', '1'])
    else: 
        # Production run
        args = arg_parser.parse_args()
    if args.verbose == 1:
        logging.getLogger().setLevel(logging.DEBUG)


    logging.info('Building tree with following arguments: %s', args)

    build_network(**args.__dict__)
