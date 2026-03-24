"""Tests for AtomyClient.fetch_tree retry logic.

Guards the behaviour added alongside the get_json regex fix:
- Non-302 HTTPErrors now trigger a cooldown-and-retry (up to _HTTP_RETRIES times)
  instead of immediately re-raising, so transient connection failures no longer
  cause nodes to be permanently dropped.
- Existing 302 (token-expiry) and happy-path behaviour must be unchanged.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

# Make common/ and network_builder/ importable.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_nb_root = os.path.join(_project_root, 'network_builder')
for _p in (_project_root, _nb_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common.exceptions import HTTPError
from nb_exceptions import NoParentException
import atomy_client as _atomy_client_module
from atomy_client import AtomyClient, TokenManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_client(get_parent_auth=None):
    """Returns an AtomyClient with a mock TokenManager."""
    token_mgr = MagicMock(spec=TokenManager)
    token_mgr.get_token.return_value = 'JSESSIONID=fake-token'
    if get_parent_auth is None:
        get_parent_auth = MagicMock(side_effect=NoParentException('root'))
    return AtomyClient(token_mgr, get_parent_auth), token_mgr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFetchTreeRetry(unittest.TestCase):
    """Verifies the retry-on-unexpected-HTTP-error behaviour of fetch_tree."""

    def test_unexpected_http_error_retries_and_eventually_raises(self):
        """An HTTPError with a non-302 status is retried _HTTP_RETRIES times,
        then re-raised once retries are exhausted."""
        client, token_mgr = _make_client()
        total_attempts = AtomyClient._HTTP_RETRIES + 1  # 3 retries + 1 initial

        with patch.object(_atomy_client_module, 'get_json',
                          side_effect=HTTPError('500')) as mock_gj:
            with self.assertRaises(HTTPError) as ctx:
                client.fetch_tree('12046345', ('user', 'pass'))

        self.assertEqual(ctx.exception.status, '500')
        self.assertEqual(mock_gj.call_count, total_attempts,
            f"Expected {total_attempts} attempts (1 initial + {AtomyClient._HTTP_RETRIES} retries)")

    def test_unexpected_http_error_retries_then_succeeds(self):
        """If the transient error clears before retries are exhausted,
        fetch_tree returns the successful result."""
        client, _ = _make_client()
        members = [{'custNo': '12046345', 'spnrNo': '', 'ptnrYn': 'N',
                    'trctLocCd': 'L', 'custNm': 'Test', 'curLvlCd': '01',
                    'mlvlCd': '01', 'corpNm': 'KR', 'joinDt': '2020-01-01',
                    'fnlSvolDt': None, 'ectrNm': None}]

        # Fail twice, succeed on the third attempt.
        with patch.object(_atomy_client_module, 'get_json',
                          side_effect=[HTTPError('503'), HTTPError('503'), members]):
            result = client.fetch_tree('12046345', ('user', 'pass'))

        self.assertEqual(result, members)

    def test_cooldown_applied_on_each_retry(self):
        """set_cooldown must be called once per retry so we back off between
        attempts rather than hammering the server."""
        client, token_mgr = _make_client()

        with patch.object(_atomy_client_module, 'get_json',
                          side_effect=HTTPError('429')):
            with self.assertRaises(HTTPError):
                client.fetch_tree('12046345', ('user', 'pass'))

        expected_cooldowns = AtomyClient._HTTP_RETRIES
        self.assertEqual(token_mgr.set_cooldown.call_count, expected_cooldowns)

    # --- existing 302 behaviour must be unchanged ---

    def test_302_triggers_token_invalidation_not_counted_as_http_retry(self):
        """A 302 (token expiry) still causes a re-login, not a retry counter
        decrement, so the two mechanisms are independent."""
        client, token_mgr = _make_client()
        members = [{'custNo': '12046345', 'spnrNo': '', 'ptnrYn': 'N',
                    'trctLocCd': 'L', 'custNm': 'Test', 'curLvlCd': '01',
                    'mlvlCd': '01', 'corpNm': 'KR', 'joinDt': '2020-01-01',
                    'fnlSvolDt': None, 'ectrNm': None}]

        with patch.object(_atomy_client_module, 'get_json',
                          side_effect=[HTTPError('302'), members]):
            result = client.fetch_tree('12046345', ('user', 'pass'))

        token_mgr.invalidate.assert_called_once()
        token_mgr.set_cooldown.assert_not_called()  # retry cooldown not triggered
        self.assertEqual(result, members)

    # --- happy path ---

    def test_successful_fetch_returns_member_list(self):
        """Nominal case: server returns a valid member list on first attempt."""
        client, _ = _make_client()
        members = [{'custNo': 'S5832131', 'spnrNo': '', 'ptnrYn': 'N',
                    'trctLocCd': 'L', 'custNm': 'Root', 'curLvlCd': '08',
                    'mlvlCd': '08', 'corpNm': 'KR', 'joinDt': '2010-01-01',
                    'fnlSvolDt': '2026-01-01', 'ectrNm': 'Seoul'}]

        with patch.object(_atomy_client_module, 'get_json', return_value=members):
            result = client.fetch_tree('S5832131', ('S5832131', 'password'))

        self.assertEqual(result, members)

    def test_empty_member_list_returns_empty(self):
        """Server returning an empty list is handled gracefully."""
        client, _ = _make_client()

        with patch.object(_atomy_client_module, 'get_json', return_value=[]):
            result = client.fetch_tree('S5832131', ('S5832131', 'password'))

        self.assertEqual(result, [])

    def test_not_a_downline_member_walks_up_auth_chain(self):
        """'Not a downline member' error triggers a switch to parent credentials."""
        parent_auth = ('PARENT', 'parentpass')
        get_parent_auth = MagicMock(return_value=parent_auth)
        client, token_mgr = _make_client(get_parent_auth=get_parent_auth)

        error_response = {'errorMessage': 'Not a downline member'}
        members = [{'custNo': '12046345', 'spnrNo': '', 'ptnrYn': 'N',
                    'trctLocCd': 'L', 'custNm': 'Test', 'curLvlCd': '01',
                    'mlvlCd': '01', 'corpNm': 'KR', 'joinDt': '2020-01-01',
                    'fnlSvolDt': None, 'ectrNm': None}]

        with patch.object(_atomy_client_module, 'get_json',
                          side_effect=[error_response, members]):
            result = client.fetch_tree('12046345', ('user', 'pass'))

        get_parent_auth.assert_called_once_with('user')
        self.assertEqual(result, members)


if __name__ == '__main__':
    unittest.main()
