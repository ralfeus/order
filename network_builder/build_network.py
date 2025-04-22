from enum import Enum
from calendar import monthrange
import cProfile
from datetime import date, datetime, timedelta
from typing import Any, Optional
import utils.logging as logging
import os, os.path
from queue import Empty, Queue
import re
import threading
from tqdm_loggable.auto import tqdm
from tqdm_loggable.tqdm_logging import tqdm_logging
from time import sleep

from neomodel import db, config

from exceptions import HTTPError
from nb_exceptions import BuildPageNodesException
from utils import get_json
from utils.atomy import atomy_login2

class ChildType(Enum):
    LEFT = 0
    RIGHT = 1

# Build selection range
today = datetime.today()
month_range = monthrange(today.year, today.month)
start_date = today.strftime('%Y%m01' if today.day < 16 else '%Y%m16')
end_date = today.strftime(f'%Y%m{15 if today.day < 16 else month_range[1]:02d}')
######
TREE_URL = 'https://kr.atomy.com/myoffice/genealogy/tree'
DATA_TEMPLATE = "level=100&dropYn=Y&otherCustNo={}"
COOLDOWN = timedelta(seconds=.8)
EMERGENCY_COOLDOWN = timedelta(seconds=4)
tokens = {}
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
logging.getLogger('neo4j').setLevel(logging.INFO)
tqdm_logging.set_log_rate(timedelta(seconds=60))    

processing_threads = 0
lock = threading.Lock()
atomy_lock = threading.Lock()
token_locks = {}
updated_nodes = 0

def build_network(user, password, root_id='S5832131', cont=False, active=True, 
                  threads=10, profile=False, nodes=0, socks5_proxy='', 
                  last_updated:date=datetime.today(), **_kwargs):
    '''Builds network of Atomy members
    
    :param str user: User name under which log in to Atomy
    :param str password: Password for loging in to Atomy
    :param str root_id: Atomy ID of the node from which start network building
    :param bool cont: indicates whether to start building from the beginning or
        continue previously interrupted operation
    :param bool active: indicates whether update only active nodes. Node is
        considered active if its PV is over 10
    :param int threads: defines number of threads to use for network building
    :param bool profile: defines whether to run performance profiling
    :param int nodes: defines number of first nodes to run update upon. If value
        is `0` all nodes are updated
    :param str socks5_proxy: address of the SOCKS5 proxy server to overcome 
        Atomy blocking some source IPs
    :param date last_updated: All nodes updated before this date will be updated
        default: today
    :raises Exception: Any unexpected error'''
    logger = logging.getLogger('build_network()')
    if not root_id:
        root_id = 'S5832131'
    if profile and not os.path.exists('profiles'):
        os.mkdir('profiles')

    exceptions = Queue()
    traversing_nodes_list = [(node[0], (node[1], node[2])) 
                             for node in sorted(
                                 _init_network(root_id, last_updated or datetime.today()),
                                 key=lambda i: i[0].replace('S', '0'))]
    traversing_nodes_set = {node[0] for node in traversing_nodes_list}
    logger.debug(traversing_nodes_list)
    logger.info("Logging in to Atomy")
    __set_token(user, password, locked=True)
    c = 0
    initial_nodes_count = len(traversing_nodes_list)
    pbar = tqdm(traversing_nodes_list)
    global processing_threads
    while nodes == 0 or updated_nodes < nodes:
        if nodes > 0:
            logger.info("%s of %s nodes are updated", updated_nodes, nodes)
        while processing_threads >= threads:
            sleep(1)
        try:
            try: # Get exception from the threads
                raise exceptions.get(block=False)
            except Empty:
                pass
            with lock:
                while traversing_nodes_list[c][0] not in traversing_nodes_set:
                    logger.debug("Node %s was already crawled. Skipping...", traversing_nodes_list[c])
                    c += 1
            node_id, auth = traversing_nodes_list[c]
            c += 1
            _update_progress(pbar, c, len(traversing_nodes_list), 
                             len(traversing_nodes_set))
            # logger.info("Processing %s (%s of %s). %s tasks are running",
            #             node_id, c, len(traversing_nodes_list),
            #             len([t for t in tasks if t.is_alive()]))
            if profile:
                thread = threading.Thread(
                    target=_profile_thread,
                    args=("Thread-" + node_id, _build_page_nodes, node_id,
                          traversing_nodes_set, traversing_nodes_list, socks5_proxy, 
                          auth, exceptions),
                    name="Thread-" + node_id)
            else:
                thread = threading.Thread(
                    target=_build_page_nodes, 
                    args=(node_id, traversing_nodes_set, traversing_nodes_list,
                          socks5_proxy, auth, exceptions),
                    name="Thread-" + node_id)

            thread.start()
            with lock:
                processing_threads += 1
        except IndexError:
            if processing_threads == 0:
                logger.info('No nodes left to check. Finishing')
                break
            logger.info('%s nodes checking is in progress. Waiting for completion',
                processing_threads)
            sleep(5)
        except KeyboardInterrupt:
            logger.info("Ctrl+C was pressed. Shutting down (running threads will be completed)...")
            break
        except BuildPageNodesException as ex:
            with lock:
                traversing_nodes_set.discard(node_id)

            if str(ex.ex) == '나의 하위회원 계보도만 조회 가능합니다.':
                logger.info("The node %s is no longer in the network. Deleting...", 
                            ex.node_id)
                db.cypher_query('''
                    MATCH (a:AtomyPerson{atomy_id: $id}) DETACH DELETE a
                ''', {'id': ex.node_id})
            else:
                logger.warning(str(ex))
        except RuntimeError as ex:
            logger.warning("Couldn't start a new thread. "
                           "Trying again and reducing amount of maximum threads")
            logger.exception(ex)
            sleep(5)
            c -= 1
            if threads >= 10:
                threads -= 5
        except Exception as ex:
            logger.exception(node_id)
            raise ex
    logger.info("Done. Added %s new nodes", len(traversing_nodes_list) - initial_nodes_count)
    _set_branches(root_id)

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

def _build_page_nodes(node_id: str, traversing_nodes_set: set[str], 
                      traversing_nodes_list: list[tuple[str, tuple[str, str]]], 
                      socks5_proxy: str, auth: tuple[str, str], exceptions: Queue):
    """Gets page for a given node tree

    :param str node_id: Atomy ID of the node
    :param set[str] traversing_nodes_set: set of nodes used to identify whether
        the node has to be added to the traversing list of not. Introduced due to
        performance reasons - search at set is much faster than in the list
    :param list[str] traversing_nodes_list: list of nodes to be
        gone through
    :param str socks5_proxy: address of the SOCKS5 proxy to use for Atomy calls
     Used because Atomy server blocks some sources.
    :param tuple[str, str] auth: Credentials to be used for Atomy API calls
    :param Queue exceptions: 
    :raises Exception: If anything bad happens"""
    logging.root.setLevel(logging.DEBUG)
    global processing_threads
    logger = logging.getLogger('_build_page_nodes()')
    for _ in range(3):
        try:
            # with atomy_lock:
            token = __get_token(auth, socks5_proxy)
            page = get_json(TREE_URL + '?' + 
                            DATA_TEMPLATE.format(node_id), 
                            headers=token + [{'Cookie': 'KR_language=en'}],
                            socks5_proxy=socks5_proxy)
                # sleep(0.75)
            if type(page) == dict and page.get('errorMessage') is not None:
                logger.debug("Account %s needs to cool down", auth[0])
                __set_token_cooldown(auth[0])
                continue
            break
        except HTTPError as ex:
            if ex.status == '302':
                logger.debug("The token for %s seems to be expired. Trying to re-login", auth[0])
                token = __set_token(auth[0], auth[1], locked=False)
        except BuildPageNodesException as ex:
            exceptions.put(ex) # The exception is to be handled in the calling thread
        except Exception as ex:
            exceptions.put(BuildPageNodesException(node_id, ex)) # The exception is to be handled in the calling thread
            with lock:
                processing_threads -= 1
            return # I don't want to raise an unhandled exception
    members: list[dict[str, Any]] = page
    logger.debug("%s elements on the page to be processed", len(members))
    
    # Update or create root node
    # if node_id == root_id:
    try:
        _save_node(members[0], '', False, logger)
        if members[0]['ptnrYn'] == 'Y':
            _get_children(
                node_id, traversing_nodes_set, traversing_nodes_list, members[0], members[1:],
                logger=logger, auth=auth
            )
        logger.debug("Done building node %s", node_id)
    except MemoryError as ex:
        exceptions.put(BuildPageNodesException(node_id, ex))
        with lock:
            processing_threads -= 1
        return
    with lock:
        processing_threads -= 1

    
def __get_token(auth: tuple[str, str], socks5_proxy: str) -> list[dict[str, str]]:
    '''Returns token to be used in the headers for the Atomy API calls
    First tries to find the token of the node in the global token list
    If not found tries to authenticate as current user.
    When token is used, the cooldown timer is reset. Token with cooldown time less then allowed
    is not used and considered not found

    :param tuple[str, str] auth: tuple of Atomy ID and password
    :param str socks5_proxy: address of the SOCKS5 proxy to use for Atomy calls
    
    :return list[dict[str, str]]: List of headers to be supplied as session token'''
    global tokens
    logger = logging.getLogger('_get_token()')
    # logger.setLevel(logging.DEBUG)
    if auth[0] not in token_locks:
        token_locks[auth[0]] = threading.Lock()
    with token_locks[auth[0]]:
        if tokens.get(auth[0]) is None:
            token = __set_token(auth[0], auth[1], locked=True)
        token = tokens[auth[0]]
        logger.debug("The token for %s was last used at %s", 
                     auth[0], token['last_used'])
        # cooldown = COOLDOWN + timedelta(seconds=0.2 * token['usage_count'])
        allowed_usage = token['last_used'] + COOLDOWN
        if allowed_usage > datetime.now():
            logger.debug("The token for %s needs to cool down. Waiting for %s seconds", 
                auth[0], 
                (allowed_usage - datetime.now()).total_seconds())
            sleep(max((allowed_usage - datetime.now()).total_seconds(), 0))
        logger.debug("Releasing the token for %s at %s", auth[0], datetime.now())
        token['last_used'] = datetime.now()
        token['usage_count'] += 1
    return [{'Cookie': token['token']}]

def __set_token(username, password, locked:bool=False) -> dict[str, str]:
    global tokens
    if not locked:
        token_locks[username].acquire()
    tokens[username] = {
        'id': username,
        'token': atomy_login2(username, password), 
        'last_used': datetime.now() - COOLDOWN, 
        'usage_count': 0
    }
    logger = logging.getLogger('__set_token()')
    logger.debug("The token for %s was set", username)
    if not locked:
        token_locks[username].release()
    return tokens[username]

def __set_token_cooldown(username: str) -> None:
    global tokens
    with token_locks[username]:
        tokens[username]['last_used'] = datetime.now() + EMERGENCY_COOLDOWN

def get_child_id(parent_id, child_type):
    result, _ = db.cypher_query(f'''
        MATCH (p:AtomyPerson {{atomy_id: '{parent_id}'}})-[:{child_type.name}_CHILD]->(c:AtomyPerson)
        RETURN c.atomy_id
    ''')
    return result[0][0] if len(result) > 0 else None

def _get_children(node_id: str, traversing_nodes_set: set[str], 
                  traversing_nodes_list: list[tuple[str, tuple[str, str]]], 
                  node_element, elements, logger, auth: tuple[str, str]):

    left = right = left_element = right_element = None
    logger.fine("Getting children for %s", node_id)
    children_elements = [e for e in elements 
                           if e['spnrNo'] == node_id ]
    for element in children_elements:
        # element_id = element['cust_no']
        if left is None:
            left_element = element
            left = _add_node(parent_id=node_id, element=element, is_left=True, 
                         logger=logger)        
        else:
            right_element = element
            right = _add_node(parent_id=node_id, element=element, is_left=True, 
                         logger=logger)    
        # if left is None:
        #     logger.debug("%s is left to %s", element_id, node_id)
        #     left_child_id = get_child_id(node_id, ChildType.LEFT)
        #     if left_child_id is None:
        #         logger.debug("%s has no left child. Adding %s", node_id, element_id)
        #         left = _get_node(element=element, parent_id=node_id, 
        #                          is_left=True, logger=logger)
        #         logger.debug("%s is added to DB as left child of %s", element_id, node_id)
        #         left_element = element
        #     else:
        #         if left_child_id != element_id:
        #             logger.warning(
        #                 "%s has %s as a left child. Will be overwritten with %s.",
        #                 node_id, left_child_id, element_id)
        #         else:
        #             logger.debug(
        #                 '%s already has %s as a left child. Updating data...',
        #                 node_id, element_id)
        #         left = _get_node(element=element, parent_id=node_id, 
        #                          is_left=True, logger=logger)
        #         left_element = element
        # else:
        #     logger.debug("%s is right to %s", element_id, node_id)
        #     right_child_id = get_child_id(node_id, ChildType.RIGHT)
        #     if right_child_id is None:
        #         logger.debug("%s has no right child. Adding %s", node_id, element_id)
        #         right = _get_node(element=element, parent_id=node_id, 
        #                             is_left=False, logger=logger)
        #         logger.debug("%s is added to DB as right child of %s", element_id, node_id)
        #         right_element = element
        #     else:
        #         if right_child_id != element_id:
        #             logger.warning(
        #                 "%s has %s as a right child. Will be overwritten with %s.",
        #                 node_id, right_child_id, element_id)
        #         else:
        #             logger.debug(
        #                 '%s already has %s as a right child. Updating data...',
        #                 node_id, element_id)
        #         right = _get_node(element=element, parent_id=node_id, 
        #                           is_left=False, logger=logger)
        #         right_element = element
    # else:
    #     # Here node is set as built
    #     # Dynamic properties are updated either set during processing this node
    #     # as child one or for root node at the very beginning of the process
    #     db.cypher_query('''
    #         MATCH (node:AtomyPerson {atomy_id: $atomy_id}) 
    #         SET
    #             node.built_tree = true
    #         ''', params={
    #             'atomy_id': node_id
    #         })
    if left is not None:
        _get_children(left, traversing_nodes_set, 
                        traversing_nodes_list, left_element, elements, 
                        logger=logger, auth=auth)
    if right is not None:
        _get_children(right, traversing_nodes_set, 
                        traversing_nodes_list, right_element, elements,
                        logger=logger, auth=auth)
    with lock:
        if left is None and node_element['ptnrYn'] == 'Y':
            # Means the element has children but they aren't found in this page
            # So the crawling will be done for this element
            if node_id not in traversing_nodes_set:
                creds = _init_network(node_id)
                if creds is not None:
                    creds = (creds[0][1], creds[0][2])
                traversing_nodes_set.add(node_id)
                traversing_nodes_list.append((node_id, creds or auth))
        else:
            logger.debug("%s is done. Removing from the crawling set", node_id)
            traversing_nodes_set.discard(node_id)

def _add_node(parent_id, element, is_left: bool, logger: logging.Logger):
    element_id = element['custNo']
    if is_left:
        child_type = ChildType.LEFT
        child_type_name = 'left'
    else:
        child_type = ChildType.RIGHT
        child_type_name = 'right'
    logger.debug("%s is left to %s", element_id, parent_id)
    if logger.getEffectiveLevel() == logging.DEBUG:
        child_id = get_child_id(parent_id, child_type)
        if child_id is None:
            logger.debug("%s has no %s child. Adding %s as a left child", 
                         parent_id, child_type_name, element_id)
        else:
            if child_id != element_id:
                logger.warning(
                    "%s has %s as a %s child. Will be overwritten with %s.",
                    parent_id, child_id, child_type_name, element_id)
            else:
                logger.debug(
                    '%s already has %s as a %s child. Updating data...',
                    parent_id, element_id, child_type_name)
    return _save_node(element=element, parent_id=parent_id, is_left=is_left, 
                     logger=logger)


def _init_network(root_id: str, last_update: date=datetime.now()) -> list[list[str]]:
    '''Returns all nodes updated before `last_update`

    :param date last_update: Date of node last update that has to be updated
    :param str root_id: Atomy ID of the root node whose tree is to update
    :returns list[list[str]]]: set of tuples of Atomy ID and branch the node
        belongs to'''
    # logger = logging.getLogger("_init_network")
    # logger.info("Getting all nodes under %s updated before %s", root_id, last_update)
    result, _ = db.cypher_query('''
        // MATCH (:AtomyPerson{atomy_id:$root})<-[:PARENT*0..]-(n:AtomyPerson) 
        // WHERE date(datetime(n.when_updated)) < date($today)
        MATCH (n:AtomyPerson{atomy_id:$root})
        RETURN n.atomy_id, n.username, n.password ORDER BY n.atomy_id_normalized
    ''', {'root': root_id, 'today': last_update})
    # result = [node for node in result]
    # logger.info("Got %s outdated nodes", len(result))
    return result

def _save_node(element: dict[str, Any], parent_id: str, is_left: bool, 
              logger: logging.Logger) -> str:
    '''Saves node in the database
    
    :param dict[str, Any] element: JSON representation of the element to be saved
    :param str parent_id: Atomy ID of the parent of the node to be saved
    :param bool is_left: specifies whether node is a left child of the parent
    :param logging.Logger logger: logger object
    :returns str: Atomy ID of the node'''
    atomy_id = element['custNo']
    with lock:
        global updated_nodes
        updated_nodes += 1
    try:
        signup_date = datetime.strptime(element['joinDt'], '%Y-%m-%d')
        last_purchase_date = datetime.strptime(element['fnlSvolDt'], '%Y-%m-%d') \
                                if element.get('fnlSvolDt') is not None \
                                else None
        # pv = element['macc_pv']
        # total_pv = 0 #int(re.search('\\d+', sel_total_pv(element)).group()) # type: ignore
        # network_pv = 0 #int(re.search('\\d+', sel_network_pv(element)).group()) # type: ignore
    except Exception as ex:
        logger.exception("_get_node(): In %s the error has happened", atomy_id)
        raise ex
    if parent_id == '':
        _save_root_node(atomy_id, element, signup_date, last_purchase_date)
    else:
        _save_child_node(atomy_id, parent_id, element, is_left,
                                signup_date, last_purchase_date)
    logger.debug('Saved node %s: {rank: %s}', atomy_id, 
                 titles.get(element['curLvlCd']))
    return atomy_id
        
def _save_root_node(atomy_id: str, element: dict[str, Any], signup_date: datetime, 
                    last_purchase_date: Optional[datetime]) -> str:
    '''Saves root node to the database
    
    :param str atomy_id: Atomy ID of the node to be saved
    :param dict[str, Any] element: JSON element obtained from Atomy and serving
        as a source of data for the database
    :param datetime signup_date: time of the node signing up to Atomy
    :param Optional[datetime] last_purchase_date: date when last purchase to
        Atomy was done
    :returns str: an Atomy ID of the node in the database'''
    db.cypher_query('''
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
        RETURN node.atomy_id
    ''', params={
        'atomy_id': atomy_id,
        'name': element['custNm'],
        'rank': titles.get(element['curLvlCd']),
        'highest_rank': titles.get(element['mlvlCd']),
        'center': element.get('ectrNm'),
        'country': element['corpNm'],
        'signup_date': signup_date,
        'last_purchase_date': last_purchase_date,
        # 'pv': pv,
        # 'total_pv': total_pv,
        # 'network_pv': network_pv,
        'now': datetime.now()
    })
    return atomy_id

def _save_child_node(atomy_id: str, parent_id: str, element, is_left: bool, 
                     signup_date: datetime, 
                     last_purchase_date: Optional[datetime]) -> str:
    '''Saves a child node to the database
    
    :param str atomy_id: Atomy ID of the node to be saved
    :param str parent_id: Atomy ID of the node's parent in the hierarchy
    :param dict[str, Any] element: JSON element obtained from Atomy and serving
        as a source of data for the database
    :param bool is_left: identifies whether the child is left leaf of the parent
    :param str branch: identifies branch of the root node where the node is.
        Possible values are: 'L', 'R'
    :param datetime signup_date: time of the node signing up to Atomy
    :param Optional[datetime] last_purchase_date: date when last purchase to
        Atomy was done
    :returns str: an Atomy ID of the node in the database'''
    db.cypher_query(f'''
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
                node.username = parent.username,
                node.password = parent.password,
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
        RETURN node.atomy_id
    ''', params={
        'atomy_id': atomy_id,
        'parent_id': parent_id,
        'name': element['custNm'],
        'rank': titles.get(element['curLvlCd']),
        'highest_rank': titles.get(element['mlvlCd']),
        'center': element.get('ectrNm'),
        'country': element['corpNm'],
        'signup_date': signup_date,
        'last_purchase_date': last_purchase_date,
        # 'pv': pv,
        # 'total_pv': total_pv,
        # 'network_pv': network_pv,
        'now': datetime.now()
    })
    return atomy_id

def _is_left(element):
    return element['trct_loc_cd'] == 'L'

def _is_right(element):
    return element['trct_loc_cd'] == 'R'

def _set_branches(root_id):
    children, _ = db.cypher_query('''
        MATCH (root:AtomyPerson{atomy_id:'S5832131'})-[:LEFT_CHILD]->(l:AtomyPerson)
        MATCH (root)-[:RIGHT_CHILD]->(r:AtomyPerson)
        RETURN l.atomy_id, r.atomy_id
    ''', {'root_id': root_id})
    db.cypher_query('''
        MATCH (:AtomyPerson{atomy_id: $id})<-[:PARENT*]-(a:AtomyPerson) SET a.branch = "L"
    ''', {'id': children[0][0]})
    db.cypher_query('''
        MATCH (:AtomyPerson{atomy_id: $id})<-[:PARENT*]-(a:AtomyPerson) SET a.branch = "R"
    ''', {'id': children[0][1]})

def _update_progress(pbar: tqdm, progress: int, total: int, left_to_crawl: int) -> None:
    pbar.total = total
    pbar.n = progress
    pbar.set_description(f"{left_to_crawl} left to crawl")
    pbar.refresh()

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
    arg_parser.add_argument('--last-updated', help="Include only nodes that were last time updated before provided date. Format: YYYY-MM-DD", 
                            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            default=date.today())
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
