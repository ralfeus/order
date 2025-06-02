from tests import BaseTestCase
from unittest.mock import patch

from exceptions import AtomyLoginError
from utils.atomy import atomy_login2, get_bu_place_from_network, invoke_curl, get_bu_place_from_page

class AtomyTest(BaseTestCase):
    def test_login2(self):
        atomy_login2('23426444', 'atomy#01')
        atomy_login2('23426444', 'atomy#01')
        with self.assertRaises(AtomyLoginError):
            atomy_login2('11111111', '1')

    def test_try_perform(self):
        pass

    @patch("utils.atomy.get_json")
    def test_get_bu_place_from_network(self, mock_get_json):
        mock_get_json.return_value = {"center_code": "12345"}
        result = get_bu_place_from_network("testuser")
        self.assertEqual(result, "12345")

    @patch("utils.atomy.atomy_login2")
    @patch("utils.atomy.invoke_curl")
    def test_get_bu_place_from_page(self, mock_curl, mock_login):
        mock_login.return_value = "jwt_token"
        mock_curl.return_value = ('\\"buPlace\\":\\"test\\"', None)
        result = get_bu_place_from_page("testuser", "testpassword")
        self.assertEqual(result, 'test')
        mock_login.assert_called_once_with("testuser", "testpassword")
        mock_curl.assert_called_once_with(
            url="https://kr.atomy.com/order/sheet",
            headers=[
                {"Cookie": "jwt_token"},
                {"referer": "https://kr.atomy.com/order/sheet"}],
            retries=0
        )
