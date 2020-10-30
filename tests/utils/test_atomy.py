from tests import BaseTestCase
from app.exceptions import AtomyLoginError
from app.utils.atomy import atomy_login

class AtomyTest(BaseTestCase):
    def test_login(self):
        atomy_login('23426444', 'atomy#01')
        with self.assertRaises(AtomyLoginError):
            atomy_login('11111111', '1')