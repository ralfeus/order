from time import sleep
from tests import BaseTestCase, app
from app.utils.browser import Browser

class BrowserTest(BaseTestCase):
    def test_create_browser(self):
        a = Browser(config=app.config)
        self.assertIsNotNone(a)
        a.get('about:blank')
        a.quit()
        sleep(1)
        self.assertRaises(Exception, lambda: a.get('about:blank'))
        a = Browser(config=app.config)
        a.get('about:blank')
        a.quit()