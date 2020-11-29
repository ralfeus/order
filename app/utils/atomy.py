import logging
from flask import current_app

from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.exceptions import AtomyLoginError
from app.utils.browser import Browser

def atomy_login(username, password, browser=None):
    local_browser = None
    if browser:
        local_browser = browser
    else:
        service_log_path = None
        service_args = None
        local_browser = Browser(config=current_app.config)
    local_browser.get('https://www.atomy.kr/v2/Home/Account/Login')
    user_field = local_browser.find_element_by_id('userId')
    password_field = local_browser.find_element_by_id('userPw')
    user_field.send_keys(username)
    password_field.send_keys(password)
    password_field.submit()
    for attempt in range(2):
        try:
            local_browser.wait_for_url('https://www.atomy.kr/v2/Home')
            return
        except UnexpectedAlertPresentException as ex:
            raise AtomyLoginError(ex)
        except Exception as ex:
            try:
                if local_browser.get_element_by_id('btnRelayPassword'):
                    __ignore_change_password(local_browser)
                else:
                    raise AtomyLoginError(ex)
            except:
                raise AtomyLoginError(ex)
        finally:
            if not browser:
                local_browser.quit()

def __ignore_change_password(browser):
    browser.get_element_by_id('btnRelayPassword').click()