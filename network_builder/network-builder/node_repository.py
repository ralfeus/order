"""Neo4j database operations for the Atomy network builder."""

import json
from datetime import date, datetime
from typing import Optional

import utils.logging as logging
from neomodel import db

from nb_exceptions import NoParentException

_VALID_CHILD_TYPES = frozenset({'LEFT_CHILD', 'RIGHT_CHILD'})


class NodeRepository:
    """Encapsulates all Neo4j read/write operations for AtomyPerson nodes."""

    def __init__(self, titles: dict) -> None:
        """
        :param titles: mapping of Atomy rank code -> rank name string.
        """
        self._titles = titles
        self._logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_nodes_to_crawl(
        self, root_id: str, last_updated: date
    ) -> list[tuple[str, tuple[str, str]]]:
        """Returns nodes in the subtree of *root_id* that need updating.

        A node needs updating when its ``when_updated`` date is strictly
        before *last_updated*. Results are sorted by normalized Atomy ID.

        :returns: list of (atomy_id, (username, password)) tuples.
        """
        result, _ = db.cypher_query(
            '''
            MATCH (:AtomyPerson{atomy_id: $root})<-[:PARENT*0..]-(n:AtomyPerson)
            WHERE date(datetime(n.when_updated)) < date($today)
            RETURN n.atomy_id, n.username, n.password
            ORDER BY n.atomy_id_normalized
            LIMIT 100
            ''',
            {'root': root_id, 'today': last_updated},
        )
        return [
            (row[0], (row[1], row[2]))
            for row in sorted(result, key=lambda r: r[0].replace('S', '0'))
        ]

    def get_children_in_db(self, member_ids: list[str]) -> dict:
        """Returns the current left/right children for each given node ID.

        :returns: {atomy_id: {'LEFT_CHILD': id_or_None, 'RIGHT_CHILD': id_or_None}}
        """
        result, _ = db.cypher_query(
            '''
            UNWIND $nodes AS node
            MATCH (n:AtomyPerson {atomy_id: node})
            OPTIONAL MATCH (n)-[:LEFT_CHILD]->(l:AtomyPerson)
            OPTIONAL MATCH (n)-[:RIGHT_CHILD]->(r:AtomyPerson)
            RETURN n.atomy_id AS id,
                   CASE WHEN l IS NULL THEN NULL ELSE l.atomy_id END AS left_child,
                   CASE WHEN r IS NULL THEN NULL ELSE r.atomy_id END AS right_child
            ''',
            {'nodes': member_ids},
        )
        return {
            row[0]: {'LEFT_CHILD': row[1], 'RIGHT_CHILD': row[2]}
            for row in result
        }

    def get_parent_auth(self, node_id: str) -> tuple[str, str]:
        """Returns (username, password) of the direct parent of *node_id*.

        :raises NoParentException: if the node has no parent in the DB.
        """
        result, _ = db.cypher_query(
            '''
            MATCH (:AtomyPerson {atomy_id: $node_id})-[:PARENT]->(p:AtomyPerson)
            RETURN p.username, p.password
            ''',
            {'node_id': node_id},
        )
        if not result:
            raise NoParentException(node_id)
        return result[0][0], result[0][1]

    def get_node_auth(self, node_id: str) -> Optional[tuple[str, str]]:
        """Returns (username, password) stored on the node itself, or None."""
        result, _ = db.cypher_query(
            '''
            MATCH (n:AtomyPerson {atomy_id: $node_id})
            RETURN n.username, n.password
            ''',
            {'node_id': node_id},
        )
        if result and result[0][0]:
            return result[0][0], result[0][1]
        return None

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save_root_node(
        self,
        atomy_id: str,
        element: dict,
        signup_date: datetime,
        last_purchase_date: Optional[datetime],
    ) -> str:
        """Creates or updates a page-root node (no parent relationship set)."""
        db.cypher_query(
            '''
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
            ''',
            params={
                'atomy_id': atomy_id,
                'name': element['custNm'],
                'rank': self._titles.get(element['curLvlCd']),
                'highest_rank': self._titles.get(element['mlvlCd']),
                'center': element.get('ectrNm'),
                'country': element['corpNm'],
                'signup_date': signup_date,
                'last_purchase_date': last_purchase_date,
                'now': datetime.now(),
            },
        )
        return atomy_id

    def save_child_nodes(self, nodes: list[dict]) -> None:
        """Batch-saves child nodes and their parent/child relationships.

        Neo4j's UNWIND does not expose nodes created in earlier iterations to
        later ones within the same query.  To handle pages where a child and
        its grandchild are both new, we process nodes in topological order:
        each pass saves only nodes whose parent already exists in the DB
        (or was saved in a previous pass), guaranteeing every MATCH succeeds.

        Relationship types cannot be parameterised in Cypher, so we emit one
        query per valid child_type to avoid injection risk.

        :raises ValueError: if any node contains an unexpected child_type.
        """
        if not nodes:
            return
        for node in nodes:
            if node['child_type'] not in _VALID_CHILD_TYPES:
                raise ValueError(f"Invalid child_type: {node['child_type']!r}")

        remaining = list(nodes)
        while remaining:
            # IDs of all nodes not yet written to the DB in this call
            not_yet_saved = {n['atomy_id'] for n in remaining}

            # Nodes whose parent is guaranteed to exist: either already in the
            # DB before this call, or saved in a previous pass of this loop.
            can_save = [n for n in remaining if n['parent_id'] not in not_yet_saved]

            if not can_save:
                self._logger.error(
                    "Could not determine save order for %d remaining nodes "
                    "(possible circular dependency): %s",
                    len(remaining),
                    [n['atomy_id'] for n in remaining],
                )
                break

            now = datetime.now()
            for child_type in _VALID_CHILD_TYPES:
                batch = [n for n in can_save if n['child_type'] == child_type]
                if not batch:
                    continue
                db.cypher_query(
                    f'''
                    UNWIND $records AS record
                    MATCH (parent:AtomyPerson {{atomy_id: record.parent_id}})
                    MERGE (node:AtomyPerson {{atomy_id: record.atomy_id}})
                    ON CREATE SET
                            node.atomy_id_normalized = REPLACE(record.atomy_id, 'S', '0'),
                            node.name = record.name,
                            node.rank = record.rank,
                            node.highest_rank = record.highest_rank,
                            node.center = record.center,
                            node.country = record.country,
                            node.signup_date = record.signup_date,
                            node.last_purchase_date = record.last_purchase_date,
                            node.username = parent.username,
                            node.password = parent.password,
                            node.when_updated = $now
                    ON MATCH SET
                            node.name = record.name,
                            node.rank = record.rank,
                            node.highest_rank = record.highest_rank,
                            node.center = record.center,
                            node.country = record.country,
                            node.last_purchase_date = record.last_purchase_date,
                            node.when_updated = $now
                    MERGE (node)-[:PARENT]->(parent)
                    MERGE (parent)-[:{child_type}]->(node)
                    RETURN node.atomy_id
                    ''',
                    params={'records': batch, 'now': now},
                )

            saved_ids = {n['atomy_id'] for n in can_save}
            remaining = [n for n in remaining if n['atomy_id'] not in saved_ids]

    def delete_node(self, node_id: str) -> None:
        """Deletes a node and all its relationships from the graph."""
        db.cypher_query(
            'MATCH (a:AtomyPerson {atomy_id: $id}) DETACH DELETE a',
            {'id': node_id},
        )

    def replace_child(self, parent_id: str, old_child_id: str) -> None:
        """Removes a child node that is about to be replaced by a new one."""
        db.cypher_query(
            'MATCH (n:AtomyPerson {atomy_id: $child_id})-[r]-() DELETE r, n',
            {'child_id': old_child_id},
        )

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def set_branches(self, root_id: str) -> None:
        """Tags every descendant with 'L' or 'R' based on which child of
        *root_id* they are under."""
        children, _ = db.cypher_query(
            '''
            MATCH (root:AtomyPerson {atomy_id: $root_id})-[:LEFT_CHILD]->(l:AtomyPerson)
            MATCH (root)-[:RIGHT_CHILD]->(r:AtomyPerson)
            RETURN l.atomy_id, r.atomy_id
            ''',
            {'root_id': root_id},
        )
        if not children:
            self._logger.warning("Root %s has no left/right children; skipping branch tagging", root_id)
            return
        db.cypher_query(
            'MATCH (:AtomyPerson {atomy_id: $id})<-[:PARENT*]-(a:AtomyPerson) SET a.branch = "L"',
            {'id': children[0][0]},
        )
        db.cypher_query(
            'MATCH (:AtomyPerson {atomy_id: $id})<-[:PARENT*]-(a:AtomyPerson) SET a.branch = "R"',
            {'id': children[0][1]},
        )

    def update_search_cache(self, root_id: str) -> None:
        """Rebuilds ``Quantity`` cache nodes used for fast filtered counts."""
        db.cypher_query('MATCH (n:Quantity) DELETE n')
        for rank in self._titles.values():
            self._logger.info("Caching count for rank: %s", rank)
            db.cypher_query(
                '''
                MATCH (:AtomyPerson {atomy_id: $root_id})<-[:PARENT*0..]-(n:AtomyPerson)
                WITH COUNT(n) AS total
                MERGE (q:Quantity {root: $root_id, filter: "", total: total})
                RETURN total
                ''',
                params={'root_id': root_id},
            )
            db.cypher_query(
                '''
                MATCH (:AtomyPerson {atomy_id: $root_id})<-[:PARENT*0..]-(n:AtomyPerson)
                WHERE n.rank = $rank
                WITH COUNT(n) AS total
                MERGE (q:Quantity {root: $root_id, filter: $params, total: total})
                RETURN total
                ''',
                params={
                    'root_id': root_id,
                    'rank': rank,
                    'params': json.dumps({'rank': rank}),
                },
            )
