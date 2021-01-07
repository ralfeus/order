from flask import current_app

from selenium.common.exceptions import NoAlertPresentException, \
    NoSuchElementException, UnexpectedAlertPresentException

from app.exceptions import AtomyLoginError
from app.utils.browser import Browser

def atomy_login(username, password, browser=None):
    logger = current_app.logger.getChild('atomy_login')
    local_browser = None
    if browser:
        local_browser = browser
    else:
        local_browser = Browser(config=current_app.config)
    logger.debug("Getting loging page")
    local_browser.get('https://www.atomy.kr/v2/Home/Account/Login')
    try:
        logger.debug("Dismissing any alerts")
        local_browser.switch_to_alert().dismiss()
    except NoAlertPresentException:
        pass
    user_field = local_browser.get_element_by_id('userId')
    password_field = local_browser.get_element_by_id('userPw')
    user_field.send_keys(username)
    password_field.send_keys(password)
    logger.debug("Submitting credentials")
    password_field.submit()
    try:
        logger.debug("Waiting for home page")
        local_browser.wait_for_url('https://www.atomy.kr/v2/Home')
        logger.debug('Login is successful')
        return
    except UnexpectedAlertPresentException as ex:
        logger.debug("Alert is %s. Login is failed", ex.args)
        raise AtomyLoginError(ex.args[0])
    except Exception as ex:
        logger.debug("Couldn't get home page")
        try:
            if local_browser.get_element_by_id('btnRelayPassword'):
                logger.debug("Password change request is found. Dismissing")
                __ignore_change_password(local_browser)
            else:
                logger.debug("The reason is unknown. Login is failed")
                raise AtomyLoginError(ex)
        except AtomyLoginError as ex:
            logger.debug('Login is failed: %s', ex.args)
            raise ex
        except NoSuchElementException:
            logger.debug("No password change request is found. Login is failed")
            raise AtomyLoginError()
    finally:
        if not browser:
            local_browser.quit()

def __ignore_change_password(browser):
    try:
        browser.get_element_by_id('btnRelayPassword').click()
    except:
        AtomyLoginError("Couldn't ignore change password")