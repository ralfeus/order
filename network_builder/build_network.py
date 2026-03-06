"""Atomy network builder — CLI entry point and top-level orchestration.

Run directly::

    python build_network.py --user <id> --password <pw> --root <root_id>

Or call :func:`build_network` programmatically from other modules.
"""

import os
import sys

_here   = os.path.dirname(os.path.abspath(__file__))  # network_builder/ (local) or /app/ (Docker)
_parent = os.path.dirname(_here)                       # project root (local) or / (Docker)
sys.path.insert(0, _here)    # Docker: /app/ has common/ → works
sys.path.insert(0, _parent)  # local: project root has common/ → works

from datetime import date, datetime, timedelta
from typing import Optional

from neomodel import config
from tqdm_loggable.tqdm_logging import tqdm_logging

import common.utils.logging as logging
from atomy_client import AtomyClient, TITLES, TokenManager
from node_repository import NodeRepository
from state_server import StateServer
from tree_crawler import TreeCrawler

# ---------------------------------------------------------------------------
# Neo4j connection (override via NEO4J_URL environment variable)
# ---------------------------------------------------------------------------
config.DATABASE_URL = os.environ.get('NEO4J_URL') or 'bolt://neo4j:1@localhost:7687'

# ---------------------------------------------------------------------------
# Logging defaults
# ---------------------------------------------------------------------------
logging.basicConfig(
    force=True,
    format='%(asctime)s\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s',
)
logging.getLogger('neo4j').setLevel(logging.INFO)
tqdm_logging.set_log_rate(timedelta(seconds=60))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_network(
    user: str,
    password: str,
    root_id: str = 'S5832131',
    roots_file: Optional[str] = None,
    active: bool = True,
    max_threads: int = 10,
    profile: bool = False,
    nodes: int = 0,
    socks5_proxy: str = '',
    last_updated: Optional[date] = None,
    repeat: bool = False,
    **_kwargs,
) -> None:
    """Builds (or updates) the Atomy member network tree in Neo4j.

    :param str user: Atomy username used for authentication.
    :param str password: Atomy password.
    :param str root_id: Atomy ID of the tree root to start from.
    :param str roots_file: Path to a tab-separated file with columns
        ``atomy_id\\tusername\\tpassword`` — alternative to ``root_id``.
    :param bool active: Reserved for future use (not currently applied).
    :param int max_threads: Maximum number of concurrent worker threads.
    :param bool profile: When True, each thread is wrapped with cProfile.
    :param int nodes: Stop after updating this many nodes (0 = unlimited).
    :param str socks5_proxy: SOCKS5 proxy address, e.g. ``localhost:9050``.
    :param date last_updated: Only update nodes whose ``when_updated`` is
        strictly before this date.  Defaults to today.
    :param bool repeat: Keep re-running until no outdated nodes remain.
    """
    logger = logging.getLogger('build_network')

    if not root_id:
        root_id = 'S5832131'
    if profile and not os.path.exists('profiles'):
        os.mkdir('profiles')

    effective_last_updated = last_updated or date.today()

    repo = NodeRepository(TITLES)
    token_manager = TokenManager(socks5_proxy=socks5_proxy)
    client = AtomyClient(token_manager, repo.get_parent_auth, socks5_proxy=socks5_proxy)
    crawler = TreeCrawler(client, repo, max_threads, profile=profile)

    if roots_file is not None:
        traversing_nodes_list = _load_roots_file(roots_file)
    else:
        traversing_nodes_list = repo.get_nodes_to_crawl(root_id, effective_last_updated)

    if not traversing_nodes_list:
        logger.info("No nodes to update. Finishing.")
        return

    with StateServer(crawler.get_state):
        while True:
            total_updated = crawler.crawl(traversing_nodes_list, nodes_limit=nodes)
            logger.info("Done. Updated %s nodes.", total_updated)

            if not repeat:
                break
            traversing_nodes_list = repo.get_nodes_to_crawl(root_id, effective_last_updated)
            if not traversing_nodes_list:
                logger.info("No outdated nodes remain. Finishing.")
                break

    logger.info("Setting branches for each node")
    repo.set_branches(root_id)

    logger.info("Updating search cache")
    repo.update_search_cache(root_id)

    logger.info("Done")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_roots_file(path: str) -> list[tuple[str, tuple[str, str]]]:
    """Parses a tab-separated roots file into the traversal-list format."""
    from tqdm_loggable.auto import tqdm
    result = []
    with open(path) as f:
        for line in tqdm(f):
            node_id, username, password = line.split('\t')
            result.append((node_id, (username, password.strip())))
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Build Atomy member network tree')
    mode = parser.add_mutually_exclusive_group()

    parser.add_argument('--user', default='S5832131', help='Atomy username')
    parser.add_argument('--password', default='mkk03020529!!', help='Atomy password')
    mode.add_argument('--root', dest='root_id', metavar='ROOT_ID',
                      help='Root node ID for network scan')
    mode.add_argument('--roots-file', help='File with list of root nodes')
    parser.add_argument('--active', action='store_true', default=False,
                        help='Build only active branches (reserved)')
    parser.add_argument('-v', '--verbose', action='count',
                        help='Increase verbosity (-v = FINE, -vv = DEBUG)')
    parser.add_argument('--max-threads', type=int, default=10,
                        help='Number of concurrent threads')
    parser.add_argument('--profile', action='store_true', default=False,
                        help='Enable per-thread CPU profiling')
    parser.add_argument('--nodes', type=int, default=0,
                        help='Limit update to first N nodes (0 = all)')
    parser.add_argument('--last-updated', metavar='YYYY-MM-DD',
                        type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                        default=date.today(),
                        help='Only update nodes last updated before this date')
    parser.add_argument('--socks5_proxy', default='',
                        help='SOCKS5 proxy address (e.g. localhost:9050)')
    parser.add_argument('--repeat', action='store_true', default=False,
                        help='Repeat until no outdated nodes remain')

    if os.environ.get('TERM_PROGRAM') == 'vscode':
        # Convenient defaults when launching from the VS Code debugger
        args = parser.parse_args([
            '--user', 'S5832131',
            '--password', 'mkk03020529!!',
            '--max-threads', '10',
            '--root', '23426444',
            '--repeat',
        ])
    else:
        args = parser.parse_args()

    if args.verbose == 1:
        logging.getLogger().setLevel(logging.FINE)
    elif args.verbose and args.verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    logging.info('Starting with arguments: %s', args)
    build_network(**args.__dict__)
    logging.info('Job done')
