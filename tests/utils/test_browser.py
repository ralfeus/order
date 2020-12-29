from time import sleep
from tests import BaseTestCase, app
from app.utils.browser import Browser

class BrowserTest(BaseTestCase):
    def test_create_browser(self):
        a = Browser(config=app.config)
        self.assertIsNotNone(a)
        a.get('about:blank')
        del a
