''' Singleton of web browser '''
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

class Browser(Chrome):
    ''' Singleton of web browser '''
    __instance = None
    __refs_num = 0

    def __new__(cls):
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

    def __init__(self):
        if self.__refs_num == 1:
            options = Options()
            options.set_headless(headless=True)
            super().__init__(chrome_options=options)
    
    @classmethod
    def __create_instanse(cls):
        Browser.__instance = super(Browser, cls).__new__(cls)

    def close(self):
        self.get('about:blank')

    def quit(self):
        Browser.__refs_num -= 1
        if Browser.__refs_num == 0:
            super().quit()
