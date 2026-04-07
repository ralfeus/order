"""Test runner for the refactored network builder.

Steps:
  1. Connect to Neo4j and remove the test subtree rooted at TEST_ROOT_ID.
  2. Run build_network() with multiple parameter combinations and report results.

Usage::

    python test_runner.py
"""

import os
import sys
import time
from datetime import date

from neomodel import config, db

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TEST_ROOT_ID = '23426444'
TEST_USER = '23426444'
TEST_PASSWORD = 'atomy#01'

NEO4J_URL = 'bolt://neo4j:1@localhost:7687'
config.DATABASE_URL = NEO4J_URL

# Test parameter combinations: (label, kwargs)
TEST_CASES: list[tuple[str, dict]] = [
    (
        'Single thread, all nodes',
        dict(max_threads=1, nodes=0, repeat=False),
    ),
    (
        '5 threads, first 10 nodes',
        dict(max_threads=5, nodes=10, repeat=False),
    ),
    (
        '10 threads, all nodes',
        dict(max_threads=10, nodes=0, repeat=False),
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _test_connection() -> bool:
    try:
        db.cypher_query('RETURN 1')
        return True
    except Exception as ex:
        print(f'ERROR: Cannot connect to Neo4j at {NEO4J_URL}: {ex}')
        return False


def _count_subtree(root_id: str) -> int:
    result, _ = db.cypher_query(
        '''
        MATCH (:AtomyPerson {atomy_id: $root})<-[:PARENT*0..]-(n:AtomyPerson)
        RETURN COUNT(n)
        ''',
        {'root': root_id},
    )
    return result[0][0] if result else 0


def clean_subtree(root_id: str, username: str, password: str) -> int:
    """Deletes all descendants of *root_id* (but keeps the root node itself
    with fresh credentials so the next crawl can start).

    Returns the number of nodes deleted.
    """
    count = _count_subtree(root_id)
    descendants = max(count - 1, 0)

    if count == 0:
        print(f'  Node {root_id} not in DB — creating it fresh.')
    else:
        print(f'  Deleting {descendants} descendants of {root_id}...')
        # Delete only descendants, not the root itself
        db.cypher_query(
            '''
            MATCH (:AtomyPerson {atomy_id: $root})<-[:PARENT*1..]-(d:AtomyPerson)
            DETACH DELETE d
            ''',
            {'root': root_id},
        )

    # (Re)create the root node with credentials and an old when_updated
    # so get_nodes_to_crawl will pick it up.
    db.cypher_query(
        '''
        MERGE (n:AtomyPerson {atomy_id: $atomy_id})
        SET n.atomy_id_normalized = REPLACE($atomy_id, 'S', '0'),
            n.username = $username,
            n.password = $password,
            n.when_updated = datetime('2000-01-01T00:00:00')
        ''',
        {'atomy_id': root_id, 'username': username, 'password': password},
    )
    remaining = _count_subtree(root_id)
    print(f'  Remaining nodes in subtree (root only): {remaining}')
    return descendants


def run_test(label: str, **kwargs) -> None:
    """Runs one build_network() combination and prints a result summary."""
    from build_network import build_network

    print(f'\n{"=" * 60}')
    print(f'TEST: {label}')
    print(f'  params: {kwargs}')
    print(f'  Cleaning subtree before run...')
    deleted = clean_subtree(TEST_ROOT_ID, TEST_USER, TEST_PASSWORD)
    print(f'  Deleted {deleted} descendant nodes.')

    start = time.perf_counter()
    try:
        build_network(
            user=TEST_USER,
            password=TEST_PASSWORD,
            root_id=TEST_ROOT_ID,
            last_updated=date.today(),
            **kwargs,
        )
        elapsed = time.perf_counter() - start
        count = _count_subtree(TEST_ROOT_ID)
        print(f'  PASSED in {elapsed:.1f}s — {count} nodes in DB')
    except Exception as ex:
        elapsed = time.perf_counter() - start
        print(f'  FAILED after {elapsed:.1f}s: {ex}')
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print('Atomy Network Builder — Test Runner')
    print(f'Neo4j: {NEO4J_URL}')
    print(f'Test root: {TEST_ROOT_ID}')

    if not _test_connection():
        sys.exit(1)

    print('\nRunning all test cases...')
    for label, kwargs in TEST_CASES:
        run_test(label, **kwargs)

    print('\nAll tests done.')


if __name__ == '__main__':
    main()
