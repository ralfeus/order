''' Singleton of web browser '''
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

    def __init__(self, headless=True, **kwargs):
        if self.__refs_num == 1:
            options = Options()
            if headless:
                options.set_headless(headless=True)
            else:
                options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            super().__init__(chrome_options=options, service_log_path='chrome.log', **kwargs)
    
    @classmethod
    def __create_instanse(cls):
        Browser.__instance = super(Browser, cls).__new__(cls)

    def get_element_by_class(self, class_name):
        try:
            return WebDriverWait(self, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, class_name)))
        except Exception as ex:
            raise Exception(f"No element with class {class_name} was found", ex)

    def get_element_by_id(self, id):
        try:
            return WebDriverWait(self, 20).until(
                EC.presence_of_element_located((By.ID, id)))
        except Exception as ex:
            raise Exception(f"No element with ID {id} was found", ex)

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
