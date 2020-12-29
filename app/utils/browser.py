''' Singleton of web browser '''
import logging
from selenium.common.exceptions import NoSuchElementException,\
    StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Browser:
    __browser = None
    __browser_kwargs = {}
    __config = {}
    __refs_num = 0

    def __init__(self, headless=True, config={}, **kwargs):
        self.__config = config
        self.__config['SELENIUM_HEADLESS'] = headless
        self.__browser_kwargs = kwargs
        self.__create_browser_instanse()

    def __del__(self):
        self.__browser.quit()
        del self.__browser
    
    def __create_browser_instanse(self):
        options = Options()
        if self.__config.get('SELENIUM_HEADLESS'):
            options.headless = True
        if self.__config.get('SELENIUM_BROWSER'):
            options.add_experimental_option(
                "debuggerAddress", self.__config['SELENIUM_BROWSER'])
        if self.__config.get('SELENIUM_DRIVER'):
            self.__browser_kwargs['executable_path'] = self.__config['SELENIUM_DRIVER']
        if self.__config.get('LOG_LEVEL') and self.__config['LOG_LEVEL'] == logging.DEBUG:
            if self.__config.get('SELENIUM_LOG_PATH'):
                self.__browser_kwargs['service_log_path'] = self.__config['SELENIUM_LOG_PATH']
            self.__browser_kwargs['service_args'] = ['--verbose']

        if not self.__browser_kwargs.get('executable_path'):
            self.__browser_kwargs['executable_path'] = '/usr/bin/chromedriver'
        self.__browser = Chrome(options=options, **self.__browser_kwargs)
        logging.debug(self.__browser)

    def __get_by(self, criterium, value):
        ignored_exceptions = (NoSuchElementException, StaleElementReferenceException,)
        try:
            return WebDriverWait(self.__browser, 20,
                ignored_exceptions=ignored_exceptions).until(
                    EC.presence_of_element_located((criterium, value)))
        except UnexpectedAlertPresentException as ex:
            raise ex
        except Exception as ex:
            raise Exception(f"No element with {criterium} {value} was found", ex)

    def doubleclick(self, element):
        ActionChains(self.__browser).double_click(element).perform()

    def execute_script(self, script, *args):
        return self.__browser.execute_script(script, *args)

    def find_element_by_xpath(self, xpath):
        return self.__browser.find_element_by_xpath(xpath)

    def find_elements_by_xpath(self, xpath):
        return self.__browser.find_elements_by_xpath(xpath)

    def find_elements_by_css_selector(self, css):
        return self.__browser.find_elements_by_css_selector(css)

    def get(self, url):
        exception = None
        for attempt in range(3):
            try:
                self.__browser.get(url)
                exception = None
                break
            except Exception as ex:
                self.quit()
                self.__create_browser_instanse()
                exception = ex
        if exception:
            raise exception

    def get_element_by_class(self, class_name):
        return self.__get_by(By.CLASS_NAME, class_name)

    def get_element_by_css(self, css):
        return self.__get_by(By.CSS_SELECTOR, css)

    def get_element_by_id(self, id):
        return self.__get_by(By.ID, id)

    def get_element_by_name(self, name):
        return self.__get_by(By.NAME, name)

    def switch_to_alert(self):
        return self.__browser.switch_to.alert

    def wait_for_url(self, url):
        try:
            WebDriverWait(self.__browser, 20).until(
                EC.url_to_be(url)
            )
        except Exception as ex:
            raise Exception(f"Didn't get URL {url}", ex)

    def close(self):
        self.__browser.get('about:blank')

    def quit(self):
        if self.__browser:
            self.__browser.quit()
            del self.__browser

    @property
    def title(self):
        return self.__browser.title
