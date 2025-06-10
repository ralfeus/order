from enum import Enum
from calendar import monthrange
import cProfile
from datetime import date, datetime, timedelta
import json
from typing import Any, Callable, Optional
import utils.logging as logging
import os, os.path
from queue import Empty, Queue
import threading
from tqdm_loggable.auto import tqdm
from tqdm_loggable.tqdm_logging import tqdm_logging
from time import sleep

from neomodel import db, config

from exceptions import HTTPError, AtomyLoginError
from nb_exceptions import BuildPageNodesException, NoParentException
from utils import get_json
from utils.atomy import atomy_login2

class ChildType(Enum):
    LEFT_CHILD = 0
    RIGHT_CHILD = 1

    def __str__(self):
        return super().__str__().split('.')[1]

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

logging.basicConfig(force=True,
    format="%(asctime)s\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s")
logging.getLogger('neo4j').setLevel(logging.INFO)
tqdm_logging.set_log_rate(timedelta(seconds=60))    

threads = 0
lock = threading.Lock()
atomy_lock = threading.Lock()
token_locks = {}
updated_nodes = 0

def build_network(user, password, root_id='S5832131', roots_file=None, active=True, 
                  max_threads=10, profile=False, nodes=0, socks5_proxy='', 
                  last_updated:date=datetime.today(), **_kwargs):
    '''Builds network of Atomy members
    
    :param str user: User name under which log in to Atomy
    :param str password: Password for loging in to Atomy
    :param str root_id: Atomy ID of the node from which start network building
    :param str roots_file: file with list of Atomy IDs to be used as roots for 
        network building
    :param bool cont: indicates whether to start building from the beginning or
        continue previously interrupted operation
    :param bool active: indicates whether update only active nodes. Node is
        considered active if its PV is over 10
    :param int max_threads: defines number of threads to use for network building
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
    if roots_file is not None:
        traversing_nodes_list = []
        traversing_nodes_set = set()
        with open(roots_file) as file:
            for node in tqdm(file):
                #node = _init_network(root.strip(), last_updated or datetime.today())
                #if len(node) > 0:
                #    node = node[0]
                #else:
                #    continue
                #print(node)
                id, username, password = node.split('\t')
                traversing_nodes_list.append((id, (username, password)))
    else:
        traversing_nodes_list = [(node[0], (node[1], node[2])) 
                             for node in sorted(
                                 _init_network(root_id, last_updated or datetime.today()),
                                 key=lambda i: i[0].replace('S', '0'))]
    traversing_nodes_set = {node[0] for node in traversing_nodes_list}
    stop_state_server = False
    server_thread = _start_state_server(
        lambda: stop_state_server, lambda: (traversing_nodes_set, updated_nodes))
    # logger.debug(traversing_nodes_list)
    c = 0
    pbar = tqdm(traversing_nodes_list)
    global threads
    while nodes == 0 or updated_nodes < nodes:
        if nodes > 0:
            logger.info("%s of %s nodes are updated", updated_nodes, nodes)
        while threads >= max_threads:
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
                threads += 1
            _update_progress(pbar, c, len(traversing_nodes_list), 
                             updated=updated_nodes)
        except IndexError:
            if threads < 1:
                logger.info('No nodes left to check. Finishing')
                break
            logger.info('%s nodes checking is in progress. Waiting for completion',
                threads)
            sleep(5)
        except KeyboardInterrupt:
            logger.info("Ctrl+C was pressed. Shutting down...")
            os._exit(0)
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
            if max_threads >= 10:
                max_threads -= 5
        except Exception as ex:
            logger.exception(node_id)
            raise ex
    logger.info("Done. Updated %s nodes", updated_nodes)
    logger.info("Setting branches for each node")
    _set_branches(root_id)
    logger.info("Done")
    stop_state_server = True
    server_thread.join()

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
    global threads
    logger = logging.getLogger('_build_page_nodes()')
    members = []
    while True:
        try:
            # with atomy_lock:
            token = _get_token(auth, socks5_proxy)
            members = get_json(TREE_URL + '?' + 
                            DATA_TEMPLATE.format(node_id), 
                            headers=token + [{'Cookie': 'KR_language=en'}],
                            socks5_proxy=socks5_proxy)
                # sleep(0.75)
            if type(members) == dict and members.get('errorMessage') is not None:
                if members['errorMessage'] == 'Not a downline member':
                    logger.debug("Couldn't find the node %s in the network of %s", node_id, auth[0])
                    logger.debug("Trying parent's creds")
                    auth = _get_parent_auth(auth[0])
                else:
                    logger.debug("Account %s needs to cool down", auth[0])
                    _set_token_cooldown(auth[0])
                continue
            break
        except HTTPError as ex:
            if ex.status == '302':
                logger.debug("The token for %s seems to be expired. Trying to re-login", 
                             auth[0])
                token = _set_token(auth[0], auth[1], locked=False)
        except BuildPageNodesException as ex:
            exceptions.put(ex) # The exception is to be handled in the calling thread
        except NoParentException as ex:
            logger.fine("The node %s wasn't found in the root's tree. Skipping...", 
                         node_id)
            break
        except Exception as ex:
            exceptions.put(BuildPageNodesException(node_id, ex)) # The exception is to be handled in the calling thread
            # with lock:
            #     threads -= 1
            break # I don't want to raise an unhandled exception

    if not isinstance(members, list) or len(members) == 0:
        logger.debug("No members found on the page for %s", node_id)
        with lock:
            threads -= 1
        return
    
    logger.debug("%s elements on the page to be processed", len(members))
    
    # Update or create root node
    # if node_id == root_id:
    try:
        _save_node(members[0], '', '', logger)
        if members[0]['ptnrYn'] == 'Y':
            _get_children(
                node_id, traversing_nodes_set, traversing_nodes_list, members[0], members[1:],
                logger=logger, auth=auth
            )
        logger.debug("Done building node %s", node_id)
    except Exception as ex:
        exceptions.put(BuildPageNodesException(node_id, ex))
    with lock:
        threads -= 1

def _get_parent_auth(node_id: str) -> tuple[str, str]:
    '''Returns credentials of the parent node

    :param str node_id: Atomy ID of the node whose parent credentials are to be obtained
    :returns tuple[str, str]: tuple of Atomy ID and password'''
    result, _ = db.cypher_query('''
        MATCH (:AtomyPerson {atomy_id: $node_id})-[:PARENT]->(p:AtomyPerson)
        RETURN p.username, p.password''', {'node_id': node_id})
    if len(result) == 0:
        raise NoParentException(node_id)
    return result[0][0], result[0][1]
    
def _get_token(auth: tuple[str, str], socks5_proxy: str) -> list[dict[str, str]]:
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
    try:
        with token_locks[auth[0]]:
            if tokens.get(auth[0]) is None:
                token = _set_token(auth[0], auth[1], locked=True)
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
    except AtomyLoginError:
        logger.debug("Couldn't log in as %s. Trying ancestor's username", auth[0])
        auth = _get_parent_auth(auth[0])
        return _get_token(auth, socks5_proxy)
    return [{'Cookie': token['token']}]

def _set_token(username, password, locked:bool=False) -> dict[str, str]:
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

def _set_token_cooldown(username: str) -> None:
    global tokens
    with token_locks[username]:
        tokens[username]['last_used'] = datetime.now() + EMERGENCY_COOLDOWN

def get_child_id(parent_id, child_type: ChildType):
    result, _ = db.cypher_query(f'''
        MATCH (p:AtomyPerson {{atomy_id: '{parent_id}'}})-[:{child_type.name}]->(c:AtomyPerson)
        RETURN c.atomy_id
    ''')
    return result[0][0] if len(result) > 0 else None

def _get_children(node_id: str, traversing_nodes_set: set[str], 
                  traversing_nodes_list: list[tuple[str, tuple[str, str]]], 
                  node_element, elements, logger, auth: tuple[str, str]) -> bool:
    '''Recursively gets children of the node and adds them to the database

    :param str node_id: Atomy ID of the node, whose children are to be obtained
    :param set[str] traversing_nodes_set: set of nodes to be traversed. 
        Nodes, which are completed are removed from the set
    :param list[str] traversing_nodes_list: list of nodes to be traversed
    :param dict[str, Any] node_element: JSON representation of the node, obtained from the Atomy page
    :param list[dict[str, Any]] elements: JSON representation of all nodes on the page
    :param logging.Logger logger: logger object
    :param tuple[str, str] auth: credentials to be used for Atomy API calls
    :returns bool: True if the node has children on the page, False otherwise.
        False means that the node has children but they are not found on the page.
        Therefore the parent node has to be added to the traversing list'''
    logger.fine("Getting children for %s", node_id)
    children_elements = [e for e in elements 
                           if e['spnrNo'] == node_id ]
    to_crawl = False
    for element in children_elements:
        # if element['custNo'] == 'S9854104':
        #     logger.warning("------------- FOUND S9854104 -------------")
        #     logger.warning("------------- Parent: %s -----------------", node_id)
        #     os._exit(0)
        child_id = _add_node(parent_id=node_id, element=element, logger=logger)        
        to_crawl |= _get_children(child_id, traversing_nodes_set, 
                    traversing_nodes_list, element, elements, 
                    logger=logger, auth=auth)
    # Determine if the node has to be added to the traversing list
    if to_crawl:
        logger.debug("The node %s has children but they are not found in this page. Adding to the traversing list", node_id)
        with lock:
            if node_id not in traversing_nodes_set:
                creds = _init_network(node_id)
                if creds is not None:
                    creds = (creds[0][1], creds[0][2])
                traversing_nodes_set.add(node_id)
                traversing_nodes_list.append((node_id, creds or auth))
    else:
        # Determine if might have children. If the node has children, the parent
        # node has to be added to the traversing list
        if len(children_elements) == 0 and node_element['ptnrYn'] == 'Y':
            # Means the element has children but they aren't found in this page
            # So the crawling will be done for this element
            return True
        else:
            logger.debug("%s is done. Removing from the crawling set", node_id)
            traversing_nodes_set.discard(node_id)
    return False

def _add_node(parent_id, element, logger: logging.OrderLogger):
    _logger:logging.OrderLogger = logging.getLogger('_add_node()') #type:ignore
    element_id = element['custNo']
    child_type = ChildType.LEFT_CHILD if element['trctLocCd'] == 'L' \
        else ChildType.RIGHT_CHILD
    _logger.debug("%s is %s to %s", element_id, child_type, parent_id)
    child_id = get_child_id(parent_id, child_type)
    if child_id is None:
        _logger.debug("%s has no %s. Adding %s as a %s", 
                        parent_id, child_type, element_id, child_type)
    else:
        if child_id != element_id:
            _logger.fine(
                "%s has %s as a %s. Will be replaced with %s. %s will be deleted",
                parent_id, child_id, child_type, element_id, child_id)
            db.cypher_query(f'''
                MATCH (n:AtomyPerson {{atomy_id: $child_id}})-[r]-() DELETE r,n
            ''', {'child_id': child_id})
        else:
            _logger.fine(
                '%s already has %s as a %s. Updating data...',
                parent_id, element_id, child_type)
    return _save_node(element=element, parent_id=parent_id, child_type=str(child_type), 
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

def _save_node(element: dict[str, Any], parent_id: str, child_type: str, 
              logger: logging.Logger) -> str:
    '''Saves node in the database
    
    :param dict[str, Any] element: JSON representation of the element to be saved
    :param str parent_id: Atomy ID of the parent of the node to be saved
    :param str child_type: specifies child type (possible values are: 'LEFT_CHILD', 'RIGHT_CHILD')
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
        _save_child_node(atomy_id, parent_id, element, child_type,
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

def _save_child_node(atomy_id: str, parent_id: str, element, child_type: str, 
                     signup_date: datetime, 
                     last_purchase_date: Optional[datetime]) -> str:
    '''Saves a child node to the database
    
    :param str atomy_id: Atomy ID of the node to be saved
    :param str parent_id: Atomy ID of the node's parent in the hierarchy
    :param dict[str, Any] element: JSON element obtained from Atomy and serving
        as a source of data for the database
    :param str child_type: identifies whether the child is left leaf of the parent
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
        MERGE (parent)-[:{child_type}]->(node)
        RETURN node.atomy_id
    ''', params={
        'atomy_id': atomy_id,
        'parent_id': parent_id,
        'child_type': child_type,
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

def _update_progress(pbar: tqdm, progress: int, total: int, updated: int) -> None:
    global threads
    pbar.total = total
    pbar.n = progress
    pbar.set_description(f"{updated} nodes are updated. {threads} threads are running")
    pbar.refresh()
    
def _start_state_server(stop: Callable, get_data: Callable) -> threading.Thread:
    def _state_server(stop: Callable, get_data) -> None:
        import socket
        logger = logging.getLogger('_state_server()')
        start_time = datetime.now()
        initial_nodes_to_crawl = len(get_data()[0])
        with socket.socket() as s:
            s.bind(('localhost', 0))
            port = s.getsockname()[1]
            os.environ['STATE_SERVER_PORT'] = str(port)
            logger.info("State server is running on port %s", port)
            s.listen(1)
            s.settimeout(1)
            while not stop():
                try:
                    conn, addr = s.accept()
                    logger.debug("Connection from %s", addr)
                    data = get_data()
                    execution_duration = datetime.now() - start_time
                    speed = len(data[0]) / execution_duration.seconds
                    response = {
                        'threads': [t.name for t in threading.enumerate()],
                        'to_crawl': len(data[0]),
                        'updated': data[1],
                        'execution_duration': execution_duration,
                        'processing_speed': f'{speed} nodes/sec',
                    }
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    conn.close()
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    logger.info("Ctrl+C was pressed. Shutting down...")
                    break
        logger.info("State server is shutting down")
    server_thread = threading.Thread(target=_state_server, name='StateServer', 
                                     args=(stop, get_data))
    server_thread.start()
    return server_thread

if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description="Build network")
    mode = arg_parser.add_mutually_exclusive_group()
    arg_parser.add_argument('--user', help="User name to log on to Atomy", default='S5832131')
    arg_parser.add_argument('--password', help="Password to log on to Atomy", default='mkk03020529!!')
    # mode.add_argument('--update', help='Update data of existing nodes', action='store_true')
    mode.add_argument('--root', dest='root_id', metavar='ROOT_ID', help="ID of the tree or subtree root for full network scan")
    mode.add_argument('--roots-file', help="File with list of roots to be used for network building")
    arg_parser.add_argument('--active', help="Build only active branches", default=False, action="store_true")
    arg_parser.add_argument('-v', '--verbose', action='count', help='Increase verbosity')
    arg_parser.add_argument('--max-threads', help="Number of threads to run", type=int, default=10)
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
    else:
        logging.getLogger().setLevel(logging.INFO)


    logging.info('Building tree with following arguments: %s', args)
    build_network(**args.__dict__)
    logging.info("Job is done")
