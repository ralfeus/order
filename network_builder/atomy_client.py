"""Atomy website client: authentication token management and tree page fetching."""

import threading
from datetime import datetime, timedelta
from time import sleep
from typing import Callable, Optional

import common.utils.logging as logging
from common.utils import get_json
from common.utils.atomy import atomy_login2
from common.exceptions import AtomyLoginError, HTTPError
from nb_exceptions import NoParentException

TITLES = {
    '01': '판매원',
    '02': '에이전트',
    '03': '세일즈마스터',
    '04': '다이아몬드마스터',
    '05': '샤론로즈마스터',
    '06': '스타마스터',
    '07': '로열마스터',
    '08': '크라운마스터',
}

TREE_URL = 'https://kr.atomy.com/myoffice/genealogy/tree'
_DATA_TEMPLATE = "level=100&dropYn=Y&otherCustNo={}"
_COOLDOWN = timedelta(seconds=0.8)
_EMERGENCY_COOLDOWN = timedelta(seconds=4)


class TokenManager:
    """Manages Atomy JWT tokens per user with rate-limiting and auto-relogin.

    Each user gets one cached token that is rate-limited to avoid hitting
    Atomy's throttle. On login failure the caller is expected to walk up
    the parent-auth chain (handled by AtomyClient).
    """

    def __init__(self, socks5_proxy: str = '') -> None:
        self._tokens: dict = {}
        self._locks: dict[str, threading.Lock] = {}
        self._socks5_proxy = socks5_proxy
        self._logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_token(self, username: str, password: str) -> str:
        """Returns the JSESSIONID cookie string for *username*.

        Blocks until the per-user cooldown has elapsed so that we never
        hit Atomy's rate limit.

        :raises AtomyLoginError: when the login request itself fails.
        """
        self._ensure_lock(username)
        with self._locks[username]:
            if self._tokens.get(username) is None:
                self._login(username, password, locked=True)
            token = self._tokens[username]
            self._logger.debug("Token for %s last used at %s", username, token['last_used'])
            wait = (token['last_used'] + _COOLDOWN - datetime.now()).total_seconds()
            if wait > 0:
                self._logger.debug("Token for %s cooling down %.2fs", username, wait)
                sleep(wait)
            self._logger.debug("Releasing token for %s at %s", username, datetime.now())
            token['last_used'] = datetime.now()
            token['usage_count'] += 1
        return self._tokens[username]['token']

    def invalidate(self, username: str) -> None:
        """Marks a token as expired so the next call re-logs in."""
        self._ensure_lock(username)
        with self._locks[username]:
            self._tokens[username] = None

    def set_cooldown(self, username: str) -> None:
        """Applies an emergency cooldown when Atomy signals rate-limiting."""
        self._ensure_lock(username)
        with self._locks[username]:
            if self._tokens.get(username):
                self._tokens[username]['last_used'] = datetime.now() + _EMERGENCY_COOLDOWN

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_lock(self, username: str) -> None:
        if username not in self._locks:
            self._locks[username] = threading.Lock()

    def _login(self, username: str, password: str, locked: bool = False) -> None:
        """Calls Atomy login and stores the resulting token."""
        if not locked:
            self._locks[username].acquire()
        self._tokens[username] = {
            'id': username,
            'token': atomy_login2(username, password, socks5_proxy=self._socks5_proxy),
            'last_used': datetime.now() - _COOLDOWN,
            'usage_count': 0,
        }
        self._logger.debug("Token set for %s", username)
        if not locked:
            self._locks[username].release()


class AtomyClient:
    """Fetches member-tree pages from the Atomy website.

    Handles token expiry (HTTP 302), rate-limiting error responses, and
    'not a downline member' errors by walking up the sponsor-auth chain.
    """

    def __init__(
        self,
        token_manager: TokenManager,
        get_parent_auth: Callable[[str], tuple[str, str]],
        socks5_proxy: str = '',
    ) -> None:
        """
        :param token_manager: shared TokenManager instance.
        :param get_parent_auth: callable(node_id) -> (username, password).
        :param socks5_proxy: optional SOCKS5 proxy address.
        """
        self._token_manager = token_manager
        self._get_parent_auth = get_parent_auth
        self._socks5_proxy = socks5_proxy
        self._logger = logging.getLogger(self.__class__.__name__)

    def fetch_tree(self, node_id: str, auth: tuple[str, str]) -> list[dict]:
        """Fetches and returns the list of member dicts for *node_id*.

        Retries transparently on token expiry or rate-limit responses.
        Falls back to the sponsor's credentials when the current user
        cannot see *node_id* in their downline.

        :raises NoParentException: when the entire auth chain is exhausted.
        :raises Exception: on any unrecoverable network or API error.
        """
        user = auth[0]
        while True:
            try:
                token_cookie, user = self._authenticate(auth)
                if user != auth[0]:
                    self._logger.debug("Parent creds (%s) used for node %s", user, node_id)
                members = get_json(
                    TREE_URL + '?' + _DATA_TEMPLATE.format(node_id),
                    headers=[{'Cookie': token_cookie}, {'Cookie': 'KR_language=en'}],
                    socks5_proxy=self._socks5_proxy,
                )
                if isinstance(members, dict) and members.get('errorMessage'):
                    if members['errorMessage'] == 'Not a downline member':
                        self._logger.debug(
                            "Node %s not in network of %s, trying parent", node_id, user
                        )
                        auth = self._get_parent_auth(auth[0])
                    else:
                        self._logger.debug("Account %s needs to cool down", user)
                        self._token_manager.set_cooldown(user)
                    continue
                return members if isinstance(members, list) else []

            except HTTPError as ex:
                if ex.status == '302':
                    self._logger.debug("Token for %s expired, re-logging in", user)
                    self._token_manager.invalidate(user)
                    continue
                raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _authenticate(self, auth: tuple[str, str]) -> tuple[str, str]:
        """Returns (cookie_token, actual_username).

        Walks up the sponsor chain when the current user's login fails.

        :raises NoParentException: when no ancestor can authenticate.
        """
        username, password = auth
        try:
            token = self._token_manager.get_token(username, password)
            return token, username
        except AtomyLoginError:
            self._logger.debug("Login failed for %s, trying parent auth", username)
            try:
                parent_auth = self._get_parent_auth(username)
                return self._authenticate(parent_auth)
            except NoParentException:
                raise NoParentException(username)
