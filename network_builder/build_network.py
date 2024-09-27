from enum import Enum
from calendar import monthrange
import cProfile
from datetime import datetime
from typing import Any, Optional
import utils.logging as logging
import os, os.path
import re
import threading
from time import sleep

from neomodel import db, config

from exceptions import AtomyLoginError
from utils import get_json
from utils.atomy import atomy_login2

from model import AtomyPerson

class ChildType(Enum):
    LEFT = 0
    RIGHT = 1

# Build selection range
today = datetime.today()
month_range = monthrange(today.year, today.month)
start_date = today.strftime('%Y-%m-01' if today.day < 16 else '%Y-%m-16')
end_date = today.strftime(f'%Y-%m-{15 if today.day < 16 else month_range[1]:02d}')
######
TREE_URL = 'https://shop-api-ga.atomy.com/svc/genealogyTree/getGenealogyTree'
DATA_TEMPLATE = "custNo={}&standardDate={}&level=100&dataType=include&_siteId=kr&_deviceType=pc&locale=ko-KR"
token = None
''' Atomy JWT token '''
titles = {
    '01':	'판매원',
    '02':	'에이전트',
    '03':	'세일즈마스터',
    '04':	'다이아몬드마스터',
    '05':	'샤론로즈마스터',
    '06':	'스타마스터',
    '07':	'로열마스터',
    '08':	'크라운마스터'
}

############# Neo4j connection ###################
config.DATABASE_URL = os.environ.get('NEO4J_URL') or 'bolt://neo4j:1@localhost:7687'

##################################################

logging.basicConfig(level=logging.INFO, force=True,
    format="%(asctime)s\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s")
lock = threading.Lock()
updated_nodes = 0

def build_network(user, password, root_id='S5832131', cont=False, active=True, 
                  threads=10, profile=False, nodes=0, socks5_proxy='', **_kwargs):
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
    global token
    token = [{'Cookie': atomy_login2(user, password, socks5_proxy)}]
    c = 0
    initial_nodes_count = len(traversing_nodes_list)
    while nodes == 0 or updated_nodes < nodes:
        if nodes > 0:
            logger.info("%s of %s nodes are updated", updated_nodes, nodes)
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
                    args=("Thread-" + node_id, _build_page_nodes, node_id, 
                          traversing_nodes_set, traversing_nodes_list, socks5_proxy),
                    name="Thread-" + node_id)
            else:
                thread = threading.Thread(
                    target=_build_page_nodes, 
                    args=(node_id, traversing_nodes_set, traversing_nodes_list,
                          socks5_proxy),
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
        except KeyboardInterrupt:
            logger.info("Ctrl+C was pressed. Shutting down (running threads will be completed)...")
            break
        except Exception as ex:
            logger.exception(node_id)
            raise ex
    logger.info("Done. Added %s new nodes", len(traversing_nodes_list) - initial_nodes_count)
    ### PV update isn't needed anymore
    ### Consider removing in the next release
    # logger.info("Updating network PV for each node")
    # result, _ = db.cypher_query('''
    #     MATCH (n:AtomyPerson) WHERE ID(n) = 0
    #     MATCH (n)<-[:PARENT*0..]-(n1)-[:LEFT_CHILD]->()
    #     WITH n1
    #     ORDER BY n1.atomy_id_normalized DESC
    #     CALL {
    #         WITH n1
    #         MATCH (l)<-[:LEFT_CHILD]-(n1)
    #         OPTIONAL MATCH (n1)-[:RIGHT_CHILD]->(r)
    #         WITH 
    #             n1, l.network_pv AS l_pv, 
    #             CASE r WHEN NULL THEN 0 ELSE r.network_pv END AS r_pv,
    #             CASE n1.total_pv WHEN NULL THEN 0 ELSE n1.total_pv END AS t_pv
    #         SET n1.network_pv = l_pv + r_pv + t_pv
    #         RETURN n1.atomy_id AS id, n1.total_pv AS t_pv, n1.network_pv AS n_pv, l_pv, r_pv
    #     }
    #     RETURN COUNT(*)
    # ''')
    # logger.info("Update result: %s", result)

def _profile_thread(thread_name, target, *args):
    profiler = cProfile.Profile()
    profiler.enable()
    target(*args)
    profiler.disable()
    profiler.dump_stats("profiles/profile-" + thread_name + '-' + datetime.now().strftime('%Y%m%d_%H%M%S'))

def _build_page_nodes(node_id, traversing_nodes_set, traversing_nodes_list, socks5_proxy):
    logger = logging.getLogger('_build_page_nodes()')
    try:
        page = get_json(TREE_URL + '?' + 
                        DATA_TEMPLATE.format(node_id, start_date), headers=token,
                        retries=3,
                        socks5_proxy=socks5_proxy)
        if page['result'] != '200':
            raise Exception(page['resultMessage'])
    except Exception as ex:
        logger.exception("Couldn't get tree page")
        raise ex
    members: list[dict[str, Any]] = page['items']['includeItems']
    logger.debug("%s elements on the page to be processed", len(members))
    
    # Update or create root node
    if node_id == args.root_id:
        _get_node(members[0], None, False, logger)
    if members[0]['ptnr_yn'] == 'Y':
        _get_children(
            node_id, traversing_nodes_set, traversing_nodes_list, members[0], members[1:],
            logger=logger
        )
    logger.debug("Done building node %s", node_id)

def get_child_id(parent_id, child_type):
    result, _ = db.cypher_query(f'''
        MATCH (p:AtomyPerson {{atomy_id: '{parent_id}'}})-[:{child_type.name}_CHILD]->(c:AtomyPerson)
        RETURN c.atomy_id
    ''')
    return result[0][0] if len(result) > 0 else None

def _get_children(node_id, traversing_nodes_set: set, traversing_nodes_list: list, node_element,
    elements, logger):

    left = right = left_element = right_element = None
    logger.fine("Getting children for %s", node_id)
    children_elements = [e for e in elements 
                           if e['spnr_no'] == node_id ]
    for element in children_elements:
        element_id = element['cust_no']
        if _is_left(element):
            logger.debug("%s is left to %s", element_id, node_id)
            left_child_id = get_child_id(node_id, ChildType.LEFT)
            if left_child_id is None:
                logger.debug("%s has no left child. Adding %s", node_id, element_id)
                left = _get_node(element=element, parent_id=node_id, is_left=True, logger=logger)
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
                left = _get_node(element=element, parent_id=node_id, is_left=True, logger=logger)
                left_element = element
        else:
            logger.debug("%s is right to %s", element_id, node_id)
            right_child_id = get_child_id(node_id, ChildType.RIGHT)
            if right_child_id is None:
                logger.debug("%s has no right child. Adding %s", node_id, element_id)
                if  left is not None:
                    right = _get_node(element=element, parent_id=node_id, is_left=False, logger=logger)
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
                right = _get_node(element=element, parent_id=node_id, is_left=False, logger=logger)
                right_element = element
    if left is None and node_element['ptnr_yn'] == 'Y':
        # Means the element has children but they aren't found in this page
        # So the crawling will be done for this element
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
                left_element, elements, 
                logger=logger)
        if right is not None:
            _get_children(right.atomy_id, traversing_nodes_set, traversing_nodes_list,
                right_element, elements,
                logger=logger)
        with lock:
            logger.debug("%s is done. Removing from the crawling set", node_id)
            traversing_nodes_set.discard(node_id)

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

def _get_node(element: dict[str, Any], parent_id, is_left, logger: logging.Logger):
    with lock:
        global updated_nodes
        updated_nodes += 1
    atomy_id = element['cust_no']
    try:
        signup_date = datetime.strptime(element['join_dt'], '%Y-%m-%d')
        last_purchase_date = datetime.strptime(element['fnl_svol_dt'], '%Y-%m-%d') \
                                if element.get('fnl_svol_dt') is not None \
                                else None
        # pv = element['macc_pv']
        # total_pv = 0 #int(re.search('\\d+', sel_total_pv(element)).group()) # type: ignore
        # network_pv = 0 #int(re.search('\\d+', sel_network_pv(element)).group()) # type: ignore
    except Exception as ex:
        logger.exception("_get_node(): In %s the error has happened", atomy_id)
        raise ex
    if parent_id is None:
        node = _save_root_node(atomy_id, element, signup_date, last_purchase_date)
    else:
        node = _save_child_node(atomy_id, parent_id, element, is_left, 
                                signup_date, last_purchase_date)
    logger.debug('Saved node %s: {rank: %s}', atomy_id, node.rank)
    return node
        
def _save_root_node(atomy_id: str, element: dict[str, Any], signup_date: datetime, 
                    last_purchase_date: Optional[datetime]) -> AtomyPerson:
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
                node.last_purchase_date = $last_purchase_date,
                node.when_updated = $now
        ON MATCH SET
                node.name = $name,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.center = $center,
                node.country = $country,
                node.last_purchase_date = $last_purchase_date,
                node.when_updated = $now
        RETURN node
    ''', params={
        'atomy_id': atomy_id,
        'name': element['cust_nm'],
        'rank': titles.get(element['cur_lvl_cd']),
        'highest_rank': titles.get(element['mlvl_cd']),
        'center': element.get('ectr_nm'),
        'country': element['corp_nm'],
        'signup_date': signup_date,
        'last_purchase_date': last_purchase_date,
        # 'pv': pv,
        # 'total_pv': total_pv,
        # 'network_pv': network_pv,
        'now': datetime.now()
    })
    return AtomyPerson.inflate(result[0][0])

def _save_child_node(atomy_id: str, parent_id: str, element, is_left: bool, 
                     signup_date: datetime, last_purchase_date: Optional[datetime]
                     ) -> AtomyPerson:
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
                node.last_purchase_date = $last_purchase_date,
                node.when_updated = $now
        ON MATCH SET
                node.name = $name,
                node.rank = $rank,
                node.highest_rank = $highest_rank,
                node.center = $center,
                node.country = $country,
                node.last_purchase_date = $last_purchase_date,
                node.when_updated = $now
        MERGE (node)-[:PARENT]->(parent)
        MERGE (parent)-[:{"LEFT" if is_left else "RIGHT"}_CHILD]->(node)
        RETURN node
    ''', params={
        'atomy_id': atomy_id,
        'parent_id': parent_id,
        'name': element['cust_nm'],
        'rank': titles.get(element['cur_lvl_cd']),
        'highest_rank': titles.get(element['mlvl_cd']),
        'center': element.get('ectr_nm'),
        'country': element['corp_nm'],
        'signup_date': signup_date,
        'last_purchase_date': last_purchase_date,
        # 'pv': pv,
        # 'total_pv': total_pv,
        # 'network_pv': network_pv,
        'now': datetime.now()
    })
    return AtomyPerson.inflate(result[0][0])

def _is_left(element):
    return element['trct_loc_cd'] == 'L'

def _is_right(element):
    return element['trct_loc_cd'] == 'R'

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
    arg_parser.add_argument('--nodes', help="Update first nodes", type=int, default=0)
    arg_parser.add_argument('--socks5_proxy', help="Address of SOCKS5 proxy server", default='')

    if os.environ.get('TERM_PROGRAM') == 'vscode':
        # Means we run in VSCode debugger
        args = arg_parser.parse_args(['--user', 'S5832131', 
                                      '--password', 'mkk03020529!!', 
                                      '--threads', '1', '--root', '35467900', 
                                      '--nodes', '4000', '-v'])
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
