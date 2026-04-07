"""Tests for get_json HTTP-status parsing.

Specifically guards against the regression where curl's HTTP/2 stream-level
diagnostic messages (e.g. "HTTP/2 stream 10 was not closed cleanly") were
matched by the old broad regex and misidentified as an HTTP status code (e.g.
10), causing nodes to be silently dropped during reruns.
"""

import sys
import os
import unittest

# Make common/ importable when running from the project root or this file directly.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from common.exceptions import HTTPError
from common.utils import get_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_curl(stdout: str, stderr: str):
    """Returns a get_data callable that always returns fixed (stdout, stderr)."""
    def get_data(url, **kwargs):
        return stdout, stderr
    return get_data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetJsonStatusRegex(unittest.TestCase):
    """Verifies that get_json parses the HTTP status code correctly from
    curl verbose (-v) stderr output in a variety of real-world scenarios."""

    # --- regression: the bug this fix addresses ---

    def test_http2_stream_error_is_not_treated_as_status_code(self):
        """HTTP/2 stream-level error lines must NOT be parsed as a status code.

        Before the fix, "HTTP/2 stream 10 was not closed cleanly" produced
        HTTPError('10'), causing nodes to be permanently skipped.
        After the fix the regex requires the curl response-header prefix "< ",
        so no match is found and the status is empty.
        """
        stderr = (
            "* Trying 1.2.3.4:443...\n"
            "* Connected to kr.atomy.com (1.2.3.4) port 443 (#0)\n"
            "* HTTP/2 stream 10 was not closed cleanly: INTERNAL_ERROR (err 2)\n"
            "* Closing connection 0\n"
        )
        with self.assertRaises(HTTPError) as ctx:
            get_json('https://kr.atomy.com/test', get_data=_mock_curl('', stderr))
        self.assertNotEqual(ctx.exception.status, '10',
            "Stream number 10 must not be mistaken for HTTP status 10")
        self.assertEqual(ctx.exception.status, '',
            "No response header line → status should be empty string")

    def test_http2_stream_5_is_not_treated_as_status_code(self):
        """Regression guard for other HTTP/2 stream numbers (e.g. 5)."""
        stderr = "* HTTP/2 stream 5 was not closed cleanly: PROTOCOL_ERROR (err 1)\n"
        with self.assertRaises(HTTPError) as ctx:
            get_json('https://kr.atomy.com/test', get_data=_mock_curl('', stderr))
        self.assertNotEqual(ctx.exception.status, '5')
        self.assertEqual(ctx.exception.status, '')

    # --- correct parsing of real HTTP response status lines ---

    def test_http2_302_redirect_is_parsed_correctly(self):
        """A genuine HTTP/2 302 is extracted from the response header line."""
        stderr = (
            "* Connected to kr.atomy.com\n"
            "< HTTP/2 302 \n"
            "< location: /login\n"
        )
        with self.assertRaises(HTTPError) as ctx:
            get_json('https://kr.atomy.com/test', get_data=_mock_curl('', stderr))
        self.assertEqual(ctx.exception.status, '302')

    def test_http11_403_is_parsed_correctly(self):
        """HTTP/1.1 response status is extracted correctly."""
        stderr = (
            "* Connected to kr.atomy.com\n"
            "< HTTP/1.1 403 Forbidden\n"
            "< content-type: text/html\n"
        )
        with self.assertRaises(HTTPError) as ctx:
            get_json('https://kr.atomy.com/test', get_data=_mock_curl('', stderr))
        self.assertEqual(ctx.exception.status, '403')

    def test_http10_status_is_parsed_correctly(self):
        """HTTP/1.0 responses (common from proxy CONNECT tunnels) are parsed."""
        stderr = "< HTTP/1.0 200 Connection established\n"
        # Status 200 + non-JSON body → Exception (not HTTPError) because
        # get_json hits the 'Unknown error' branch when retries=0.
        with self.assertRaises(Exception):
            get_json('https://kr.atomy.com/test',
                     get_data=_mock_curl('<html>not json</html>', stderr))

    def test_connection_failure_gives_empty_status(self):
        """When curl never receives an HTTP response (e.g. connection refused)
        the status is empty, not some spurious number."""
        stderr = (
            "* connect to 1.2.3.4 port 443 failed: Connection refused\n"
            "curl: (7) Failed to connect to kr.atomy.com port 443\n"
        )
        with self.assertRaises(HTTPError) as ctx:
            get_json('https://kr.atomy.com/test', get_data=_mock_curl('', stderr))
        self.assertEqual(ctx.exception.status, '')

    # --- happy path ---

    def test_valid_json_200_is_returned(self):
        """Valid JSON with HTTP 200 response is returned without exception."""
        stderr = (
            "* Connected to kr.atomy.com\n"
            "< HTTP/2 200 \n"
            "< content-type: application/json\n"
        )
        result = get_json('https://kr.atomy.com/test',
                          get_data=_mock_curl('[{"custNo": "123"}]', stderr))
        self.assertEqual(result, [{'custNo': '123'}])

    def test_stream_error_before_real_response_line_uses_real_status(self):
        """If stderr contains BOTH a stream error AND a proper response header,
        only the response header is matched (stream line has no '< ' prefix)."""
        stderr = (
            "* HTTP/2 stream 10 was not closed cleanly: INTERNAL_ERROR (err 2)\n"
            "< HTTP/2 200 \n"
            "< content-type: application/json\n"
        )
        result = get_json('https://kr.atomy.com/test',
                          get_data=_mock_curl('{"ok": true}', stderr))
        self.assertEqual(result, {'ok': True})


if __name__ == '__main__':
    unittest.main()
