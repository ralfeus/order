"""TCP state-reporting server for monitoring the network build progress."""

import json
import socket
import threading
from datetime import datetime
from typing import Callable

import utils.logging as logging


class StateServer:
    """Listens on a random TCP port and responds with build progress JSON.

    Usage as a context manager::

        with StateServer(crawler.get_state) as server:
            crawler.crawl(nodes)

    Or manually::

        server = StateServer(crawler.get_state)
        port = server.start()
        ...
        server.stop()

    The response JSON has the shape::

        {
            "threads": ["Thread-A", ...],
            "threads_count": 3,
            "to_crawl": 42,
            "updated": 100,
            "execution_duration": "0:01:23",
            "processing_speed": "1.23 nodes/sec"
        }
    """

    def __init__(self, get_data: Callable[[], tuple[set, int, int]]) -> None:
        """
        :param get_data: callable returning (traversing_set, updated_count, threads_count).
        """
        self._get_data = get_data
        self._stop = False
        self._port = 0
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> int:
        """Starts the server in a daemon thread and returns the port number."""
        self._stop = False
        port_ready = threading.Event()
        self._thread = threading.Thread(
            target=self._serve,
            args=(port_ready,),
            name='StateServer',
            daemon=True,
        )
        self._thread.start()
        port_ready.wait()
        return self._port

    def stop(self) -> None:
        """Signals the server to stop and waits for the thread to exit."""
        self._stop = True
        if self._thread:
            self._thread.join()

    def __enter__(self) -> 'StateServer':
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Server loop (runs inside the daemon thread)
    # ------------------------------------------------------------------

    def _serve(self, port_ready: threading.Event) -> None:
        start_time = datetime.now()
        initial_count: int | None = None

        with socket.socket() as s:
            s.bind(('localhost', 0))
            self._port = s.getsockname()[1]
            self._logger.info("State server listening on localhost:%s", self._port)
            port_ready.set()
            s.listen(1)
            s.settimeout(1)

            while not self._stop:
                try:
                    conn, addr = s.accept()
                    self._logger.debug("Connection from %s", addr)

                    data = self._get_data()

                    # Lazily capture the initial queue size on first connection
                    if initial_count is None:
                        initial_count = len(data[0])

                    duration = datetime.now() - start_time
                    elapsed = max(duration.total_seconds(), 1)
                    speed = (initial_count - len(data[0])) / elapsed

                    response = {
                        'threads': [t.name for t in threading.enumerate()],
                        'threads_count': data[2],
                        'to_crawl': len(data[0]),
                        'updated': data[1],
                        'execution_duration': str(duration),
                        'processing_speed': f'{speed:.3} nodes/sec',
                    }
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    conn.close()

                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    self._logger.info("Ctrl+C — shutting down state server.")
                    break

        self._logger.info("State server stopped.")
