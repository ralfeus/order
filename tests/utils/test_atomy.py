from tests import BaseTestCase
from exceptions import AtomyLoginError
from utils.atomy import atomy_login

class AtomyTest(BaseTestCase):
    def test_login(self):
        atomy_login('23426444', 'atomy#01', run_browser=False)
        atomy_login('23426444', 'atomy#01', run_browser=False)
        with self.assertRaises(AtomyLoginError):
            atomy_login('11111111', '1', run_browser=False)
