from tests import BaseTestCase
from unittest.mock import patch

from common.exceptions import AtomyLoginError
from common.utils.atomy import atomy_login2, get_bu_place_from_network, invoke_curl, get_bu_place_from_page

class AtomyTest(BaseTestCase):
    def test_login2(self):
        atomy_login2('23426444', 'atomy#01')
        atomy_login2('23426444', 'atomy#01')
        with self.assertRaises(AtomyLoginError):
            atomy_login2('11111111', '1')

    def test_try_perform(self):
        pass
 