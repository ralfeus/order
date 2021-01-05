from flask import current_app

from selenium.common.exceptions import NoAlertPresentException, \
    NoSuchElementException, UnexpectedAlertPresentException
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
    current_app.logger.debug("atomy.atomy_login(): Getting loging page")
    local_browser.get('https://www.atomy.kr/v2/Home/Account/Login')
    try:
        current_app.logger.debug("atomy.atomy_login(): Dismissing any alerts")
        local_browser.switch_to_alert().dismiss()
    except NoAlertPresentException:
        pass
    user_field = local_browser.get_element_by_id('userId')
    password_field = local_browser.get_element_by_id('userPw')
    user_field.send_keys(username)
    password_field.send_keys(password)
    current_app.logger.debug("atomy.atomy_login(): Submitting credentials")
    password_field.submit()
    try:
        current_app.logger.debug("atomy.atomy_login(): Waiting for home page")
        local_browser.wait_for_url('https://www.atomy.kr/v2/Home')
        current_app.logger.debug('atomy.atomy_login(): Login is successful')
        return
    except UnexpectedAlertPresentException as ex:
        current_app.logger.debug("atomy.atomy_login(): Alert is %s. Login is failed", ex.args)
        raise AtomyLoginError(ex)
    except Exception as ex:
        current_app.logger.debug("atomy.atomy_login(): Couldn't get home page")
        try:
            if local_browser.get_element_by_id('btnRelayPassword'):
                current_app.logger.debug("atomy.atomy_login(): Password change request is found. Dismissing")
                __ignore_change_password(local_browser)
            else:
                current_app.logger.debug("atomy.atomy_login(): The reason is unknown. Login is failed")
                raise AtomyLoginError(ex)
        except AtomyLoginError as ex:
            current_app.logger.debug('atomy.atomy_login(): Login is failed: %s', ex.args)
            raise ex
        except NoSuchElementException:
            current_app.logger.debug("atomy.atomy_login(): No password change request is found. Login is failed")
            raise AtomyLoginError()
    finally:
        if not browser:
            local_browser.quit()

def __ignore_change_password(browser):
    try:
        browser.get_element_by_id('btnRelayPassword').click()
    except:
        AtomyLoginError("Couldn't ignore change password")