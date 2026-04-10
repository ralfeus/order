"""Tree traversal and thread management for the Atomy network builder."""

import cProfile
import os
import threading
from datetime import date, datetime
from queue import Empty, Queue
from time import sleep
from typing import Optional

from tqdm_loggable.auto import tqdm

import common.utils.logging as logging
from atomy_client import AtomyClient, TITLES
from nb_exceptions import BuildPageNodesException, NoParentException
from node_repository import NodeRepository


class TreeCrawler:
    """Crawls the Atomy member tree using a configurable thread pool.

    Each node in the traversal list is processed by one worker thread that:
    1. Fetches the member page from Atomy via ``AtomyClient``.
    2. Persists all discovered nodes to Neo4j via ``NodeRepository``.
    3. Appends any newly-discovered subtree roots to the traversal list
       so they are visited in subsequent iterations.
    """

    def __init__(
        self,
        client: AtomyClient,
        repository: NodeRepository,
        max_threads: int,
        profile: bool = False,
    ) -> None:
        self._client = client
        self._repo = repository
        self._max_threads = max_threads
        self._profile = profile

        self._lock = threading.Lock()
        self._threads: int = 0
        self._updated_nodes: int = 0
        self._exceptions: Queue = Queue()

        # Shared traversal state — initialised per crawl() call
        self._traversing_nodes_set: set[str] = set()
        self._traversing_nodes_list: list[tuple[str, tuple]] = []

        self._logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def updated_nodes(self) -> int:
        return self._updated_nodes

    @property
    def threads(self) -> int:
        return self._threads

    def get_state(self) -> tuple[set, int, int]:
        """Returns (traversing_nodes_set, updated_nodes, threads) for monitoring."""
        return self._traversing_nodes_set, self._updated_nodes, self._threads

    def find_parent(
        self,
        target_id: str,
        traversing_nodes_list: list[tuple[str, tuple]],
    ) -> Optional[str]:
        """Finds the direct parent of *target_id* by crawling the tree.

        Same traversal logic as :meth:`crawl` but:
        - no database writes are performed, and
        - the crawl stops as soon as *target_id* is found.

        :param target_id: Atomy ID of the node whose parent is sought.
        :param traversing_nodes_list: Starting (atomy_id, (username, password)) pairs.
        :returns: Atomy ID of the direct parent, or ``None`` if not found.
        """
        self._traversing_nodes_list = list(traversing_nodes_list)
        self._traversing_nodes_set = {node[0] for node in traversing_nodes_list}
        self._threads = 0
        self._exceptions = Queue()

        found_event = threading.Event()
        found_parent: list[Optional[str]] = [None]

        c = 0
        while not found_event.is_set():
            while self._threads >= self._max_threads and not found_event.is_set():
                sleep(1)

            if found_event.is_set():
                break

            try:
                self._raise_pending_exception()

                with self._lock:
                    while (
                        c < len(self._traversing_nodes_list)
                        and self._traversing_nodes_list[c][0] not in self._traversing_nodes_set
                    ):
                        c += 1

                if c >= len(self._traversing_nodes_list):
                    raise IndexError

                node_id, auth = self._traversing_nodes_list[c]
                c += 1
                thread = threading.Thread(
                    target=self._find_parent_worker,
                    args=(node_id, auth, target_id, found_event, found_parent),
                    name=f"FindParent-{node_id}",
                )
                thread.start()
                with self._lock:
                    self._threads += 1

            except IndexError:
                if self._threads < 1:
                    break
                sleep(5)

            except KeyboardInterrupt:
                self._logger.info("Ctrl+C — shutting down.")
                break

        while self._threads > 0:
            sleep(1)

        return found_parent[0]

    def crawl(
        self,
        traversing_nodes_list: list[tuple[str, tuple]],
        nodes_limit: int = 0,
    ) -> int:
        """Processes all nodes using the worker thread pool.

        :param traversing_nodes_list: (atomy_id, (username, password)) pairs to visit.
        :param nodes_limit: stop after updating this many nodes (0 = unlimited).
        :returns: total number of nodes updated in this run.
        """
        self._traversing_nodes_list = traversing_nodes_list
        self._traversing_nodes_set = {node[0] for node in traversing_nodes_list}
        self._updated_nodes = 0
        self._threads = 0
        self._exceptions = Queue()

        pbar = tqdm(traversing_nodes_list)
        c = 0

        while nodes_limit == 0 or self._updated_nodes < nodes_limit:
            if nodes_limit > 0:
                self._logger.info("%s of %s nodes updated", self._updated_nodes, nodes_limit)

            while self._threads >= self._max_threads:
                sleep(1)

            try:
                self._raise_pending_exception()

                # Advance past already-processed nodes
                with self._lock:
                    while (
                        c < len(self._traversing_nodes_list)
                        and self._traversing_nodes_list[c][0] not in self._traversing_nodes_set
                    ):
                        self._logger.debug(
                            "Node %s already crawled, skipping",
                            self._traversing_nodes_list[c][0],
                        )
                        c += 1

                if c >= len(self._traversing_nodes_list):
                    raise IndexError

                node_id, auth = self._traversing_nodes_list[c]
                c += 1
                self._start_worker(node_id, auth)
                self._update_progress(pbar, c, len(self._traversing_nodes_list))

            except IndexError:
                if self._threads < 1:
                    self._logger.info("No nodes left to process. Done.")
                    break
                self._logger.info("%s nodes still in-flight. Waiting...", self._threads)
                sleep(5)

            except KeyboardInterrupt:
                self._logger.info("Ctrl+C — shutting down.")
                os._exit(0)

            except BuildPageNodesException as ex:
                with self._lock:
                    self._traversing_nodes_set.discard(ex.node_id)
                if str(ex.ex) == '나의 하위회원 계보도만 조회 가능합니다.':
                    self._logger.info(
                        "Node %s is no longer in network. Deleting.", ex.node_id
                    )
                    self._repo.delete_node(ex.node_id)
                else:
                    self._logger.exception(str(ex), exc_info=ex)

            except NoParentException as ex:
                self._logger.info(
                    "Node %s has no parent in network. Deleting.", ex.node_id
                )
                self._repo.delete_node(ex.node_id)

            except RuntimeError as ex:
                self._logger.warning("Could not start thread; reducing max_threads. %s", ex)
                sleep(5)
                c -= 1
                if self._max_threads >= 10:
                    self._max_threads -= 5

            except Exception as ex:
                self._logger.exception("Unexpected error on node %s", node_id)
                raise

        return self._updated_nodes

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    def _start_worker(self, node_id: str, auth: tuple) -> None:
        if self._profile:
            thread = threading.Thread(
                target=self._profile_worker,
                args=(node_id, auth),
                name="Thread-" + node_id,
            )
        else:
            thread = threading.Thread(
                target=self._process_node,
                args=(node_id, auth),
                name="Thread-" + node_id,
            )
        thread.start()
        with self._lock:
            self._threads += 1

    def _profile_worker(self, node_id: str, auth: tuple) -> None:
        profiler = cProfile.Profile()
        profiler.enable()
        self._process_node(node_id, auth)
        profiler.disable()
        profiler.dump_stats(f"profiles/profile-Thread-{node_id}-{datetime.now():%Y%m%d_%H%M%S}")

    # ------------------------------------------------------------------
    # Node processing (runs inside a worker thread)
    # ------------------------------------------------------------------

    def _process_node(self, node_id: str, auth: tuple) -> None:
        """Fetches the Atomy page for *node_id* and saves all children to Neo4j."""
        try:
            try:
                members = self._client.fetch_tree(node_id, auth)
            except NoParentException as ex:
                self._logger.fine(  # type: ignore[attr-defined]
                    "Node %s not found in root tree. Skipping.", node_id
                )
                self._exceptions.put(
                    NoParentException(node_id).with_traceback(ex.__traceback__)
                )
                return
            except Exception as ex:
                self._exceptions.put(
                    BuildPageNodesException(node_id, ex).with_traceback(ex.__traceback__)
                )
                return

            if not members:
                self._logger.debug("No members returned for %s", node_id)
                return

            self._logger.debug("%s members to process for %s", len(members), node_id)

            children_in_db = self._repo.get_children_in_db(
                [m['custNo'] for m in members]
            )
            nodes_to_save: list[dict] = []

            self._collect_node(members[0], parent_id='', child_type='', nodes_to_save=nodes_to_save)
            if members[0]['ptnrYn'] == 'Y':
                self._get_children(
                    node_id=node_id,
                    node_element=members[0],
                    elements=members[1:],
                    auth=auth,
                    nodes_to_save=nodes_to_save,
                    children_in_db=children_in_db,
                )

            self._logger.debug("Saving %s nodes for %s", len(nodes_to_save), node_id)
            self._repo.save_child_nodes(nodes_to_save)
            self._logger.debug("Finished processing %s", node_id)

        except Exception as ex:
            self._exceptions.put(
                BuildPageNodesException(node_id, ex).with_traceback(ex.__traceback__)
            )
        finally:
            with self._lock:
                self._threads -= 1

    def _find_parent_worker(
        self,
        node_id: str,
        auth: tuple,
        target_id: str,
        found_event: threading.Event,
        result: list,
    ) -> None:
        """Worker thread for :meth:`find_parent` — no DB writes."""
        try:
            if found_event.is_set():
                return

            try:
                members = self._client.fetch_tree(node_id, auth)
            except NoParentException:
                with self._lock:
                    self._traversing_nodes_set.discard(node_id)
                return
            except Exception as ex:
                self._exceptions.put(
                    BuildPageNodesException(node_id, ex).with_traceback(ex.__traceback__)
                )
                return

            if not members:
                with self._lock:
                    self._traversing_nodes_set.discard(node_id)
                return

            # Check if target appears anywhere on this page
            for member in members[1:]:
                if member['custNo'] == target_id:
                    with self._lock:
                        if not found_event.is_set():
                            result[0] = member['spnrNo']
                            found_event.set()
                    return

            if found_event.is_set():
                return

            # Target not on this page — enqueue subtrees with off-page children
            if members[0]['ptnrYn'] == 'Y':
                self._search_enqueue_children(
                    node_id=node_id,
                    node_element=members[0],
                    elements=members[1:],
                    auth=auth,
                )
            else:
                with self._lock:
                    self._traversing_nodes_set.discard(node_id)

        except Exception as ex:
            self._exceptions.put(
                BuildPageNodesException(node_id, ex).with_traceback(ex.__traceback__)
            )
        finally:
            with self._lock:
                self._threads -= 1

    def _search_enqueue_children(
        self,
        node_id: str,
        node_element: dict,
        elements: list[dict],
        auth: tuple,
    ) -> bool:
        """Enqueues nodes with off-page children for the parent search.

        Mirrors :meth:`_get_children` without any database writes.

        :returns: ``True`` when *node_id* has children not present on this page,
                  signalling the caller to enqueue *node_id* for a deeper fetch.
        """
        children_on_page = [e for e in elements if e['spnrNo'] == node_id]
        needs_deeper_crawl = False

        for element in children_on_page:
            child_id = element['custNo']
            needs_deeper_crawl |= self._search_enqueue_children(
                node_id=child_id,
                node_element=element,
                elements=elements,
                auth=auth,
            )

        if needs_deeper_crawl:
            self._enqueue_for_crawl(node_id, auth)
            return False

        if not children_on_page and node_element['ptnrYn'] == 'Y':
            return True

        # Fully explored on this page
        with self._lock:
            self._traversing_nodes_set.discard(node_id)
        return False

    def _get_children(
        self,
        node_id: str,
        node_element: dict,
        elements: list[dict],
        auth: tuple,
        nodes_to_save: list[dict],
        children_in_db: dict,
    ) -> bool:
        """Recursively collects children of *node_id* from the page data.

        :returns: True when *node_id* has children not present on this page,
                  signalling the caller that *node_id*'s parent must be
                  added to the traversal list.
        """
        self._logger.fine("Getting children for %s", node_id)  # type: ignore[attr-defined]
        children_on_page = [e for e in elements if e['spnrNo'] == node_id]
        needs_deeper_crawl = False

        for element in children_on_page:
            child_id = self._add_child_node(node_id, element, nodes_to_save, children_in_db)
            needs_deeper_crawl |= self._get_children(
                node_id=child_id,
                node_element=element,
                elements=elements,
                auth=auth,
                nodes_to_save=nodes_to_save,
                children_in_db=children_in_db,
            )

        if needs_deeper_crawl:
            self._logger.debug("Node %s has off-page children; adding to traversal.", node_id)
            self._enqueue_for_crawl(node_id, auth)
            return False

        if not children_on_page and node_element['ptnrYn'] == 'Y':
            # This node has children somewhere, but they aren't on this page.
            # Signal the parent to add this node to the traversal list.
            self._logger.debug("Node %s has children not on this page; signalling parent.", node_id)
            return True

        # Node is fully processed.
        self._logger.debug("Node %s done; removing from traversal set.", node_id)
        self._traversing_nodes_set.discard(node_id)
        return False

    def _add_child_node(
        self,
        parent_id: str,
        element: dict,
        nodes_to_save: list[dict],
        children_in_db: dict,
    ) -> str:
        """Registers a child node for saving, replacing the old child if needed."""
        element_id = element['custNo']
        child_type = 'LEFT_CHILD' if element['trctLocCd'] == 'L' else 'RIGHT_CHILD'
        self._logger.debug("%s is %s of %s", element_id, child_type, parent_id)

        current_child = children_in_db.get(parent_id, {}).get(child_type)
        if current_child is not None and current_child != element_id:
            self._logger.fine(  # type: ignore[attr-defined]
                "%s: replacing %s (%s) with %s",
                parent_id, current_child, child_type, element_id,
            )
            self._repo.replace_child(parent_id, current_child)

        return self._collect_node(element, parent_id, child_type, nodes_to_save)

    def _collect_node(
        self,
        element: dict,
        parent_id: str,
        child_type: str,
        nodes_to_save: list[dict],
    ) -> str:
        """Parses *element* and either saves it immediately (root) or queues it.

        Root nodes (``parent_id == ''``) are written to the DB right away so
        that subsequent child nodes can reference them as parents.
        """
        atomy_id = element['custNo']
        with self._lock:
            self._updated_nodes += 1

        try:
            signup_date = datetime.strptime(element['joinDt'], '%Y-%m-%d')
            last_purchase_date = (
                datetime.strptime(element['fnlSvolDt'], '%Y-%m-%d')
                if element.get('fnlSvolDt')
                else None
            )
        except Exception:
            self._logger.exception("Error parsing dates for node %s", atomy_id)
            raise

        if not parent_id:
            self._logger.debug("Saving root node %s with data: %s", atomy_id, element)
            self._repo.save_root_node(atomy_id, element, signup_date, last_purchase_date)
        else:
            nodes_to_save.append({
                'name': element['custNm'],
                'atomy_id': atomy_id,
                'parent_id': parent_id,
                'highest_rank': TITLES.get(element['mlvlCd']),
                'highest_rank_maintenance_count': element.get('mlvlMntnTcnt', 0),
                'grade': element['custGrdNm'],
                'rank': TITLES.get(element['curLvlCd']),
                'verified': element['authYn'] == 'Y',
                'center': element.get('ectrNm'),
                'country': element['corpNm'],
                'child_type': child_type,
                'signup_date': signup_date,
                'last_purchase_date': last_purchase_date
            })

        self._logger.debug("Collected node %s (rank: %s)", atomy_id, TITLES.get(element['curLvlCd']))
        return atomy_id

    # ------------------------------------------------------------------
    # Traversal list helpers
    # ------------------------------------------------------------------

    def _enqueue_for_crawl(self, node_id: str, fallback_auth: tuple) -> None:
        """Adds *node_id* to the traversal list if not already present."""
        with self._lock:
            if node_id not in self._traversing_nodes_set:
                creds = self._repo.get_node_auth(node_id) or fallback_auth
                self._traversing_nodes_set.add(node_id)
                self._traversing_nodes_list.append((node_id, creds))

    # ------------------------------------------------------------------
    # Exception relay
    # ------------------------------------------------------------------

    def _raise_pending_exception(self) -> None:
        """Re-raises any exception that a worker thread put in the queue."""
        try:
            ex = self._exceptions.get(block=False)
            raise ex.with_traceback(ex.__traceback__)
        except Empty:
            pass

    # ------------------------------------------------------------------
    # Progress display
    # ------------------------------------------------------------------

    def _update_progress(self, pbar: tqdm, progress: int, total: int) -> None:
        pbar.total = total
        pbar.n = progress
        pbar.set_description(
            f"{self._updated_nodes} nodes updated, {self._threads} threads running"
        )
        pbar.refresh()
