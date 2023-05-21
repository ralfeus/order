from tests import BaseTestCase
from exceptions import AtomyLoginError
from utils.atomy import atomy_login2

class AtomyTest(BaseTestCase):
    def test_login2(self):
        atomy_login2('23426444', 'atomy#01')
        atomy_login2('23426444', 'atomy#01')
        with self.assertRaises(AtomyLoginError):
            atomy_login2('11111111', '1')

    # def test_multiple_login(self):
    #     for attempt in range(20):
    #         print(f"Attempt {attempt} of 99")
    #         atomy_login('23426444', 'atomy#01', run_browser=False)
