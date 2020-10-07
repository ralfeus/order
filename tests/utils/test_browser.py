from tests import BaseTestCase
from app.utils.browser import Browser

class BrowserTest(BaseTestCase):
    def test_create_browser(self):
        a = Browser()
        self.assertIsNotNone(a)
        b = Browser()
        self.assertEqual(a, b)
        b.quit()
        a.get('about:blank')
        a.quit()
        self.assertRaises(Exception, lambda: a.get('about:blank'))
        a = Browser()
        a.get('about:blank')
        a.quit()