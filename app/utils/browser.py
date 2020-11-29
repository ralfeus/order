''' Singleton of web browser '''
from selenium.common.exceptions import NoSuchElementException,\
    StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Browser(Chrome):
    ''' Singleton of web browser '''
    __instance = None
    __refs_num = 0

    def __new__(cls, headless=True, **kwargs):
        if Browser.__instance is None:
            Browser.__create_instanse()
        else:
            try:
                Browser.__instance.get('about:blank')
            except:
                Browser.__instance.quit()
                Browser.__refs_num = 0
                Browser.__create_instanse()
        Browser.__refs_num += 1
        return Browser.__instance

    def __init__(self, headless=True, connect_to=None, **kwargs):
        if self.__refs_num == 1:
            options = Options()
            if headless:
                options.set_headless(headless=True)
            if connect_to:
                options.add_experimental_option("debuggerAddress", connect_to)
            if not kwargs.get('executable_path'):
                kwargs['executable_path'] = '/usr/bin/chromedriver'
            super().__init__(chrome_options=options, service_log_path='chrome.log', **kwargs)
    
    @classmethod
    def __create_instanse(cls):
        Browser.__instance = super(Browser, cls).__new__(cls)

    def __get_by(self, criterium, value):
        ignored_exceptions = (NoSuchElementException, StaleElementReferenceException,)
        try:
            return WebDriverWait(self, 20, ignored_exceptions=ignored_exceptions).until(
                EC.presence_of_element_located((criterium, value)))
        except UnexpectedAlertPresentException as ex:
            raise ex
        except Exception as ex:
            raise Exception(f"No element with {criterium} {value} was found", ex)

    def get_element_by_class(self, class_name):
        return self.__get_by(By.CLASS_NAME, class_name)

    def get_element_by_css(self, css):
        return self.__get_by(By.CSS_SELECTOR, css)

    def get_element_by_id(self, id):
        return self.__get_by(By.ID, id)

    def get_element_by_name(self, name):
        return self.__get_by(By.NAME, name)

    def wait_for_url(self, url):
        try:
            WebDriverWait(self, 20).until(
                EC.url_to_be(url)
            )
        except Exception as ex:
            raise Exception(f"Didn't get URL {url}", ex)

    def close(self):
        self.get('about:blank')

    def quit(self):
        Browser.__refs_num -= 1
        if Browser.__refs_num == 0:
            super().quit()
