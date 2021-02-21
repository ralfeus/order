import itertools
import re
import subprocess

import lxml.html
from flask import current_app

from selenium.common.exceptions import NoAlertPresentException, \
    NoSuchElementException, UnexpectedAlertPresentException

from app.exceptions import AtomyLoginError
from app.utils.browser import Browser

def _atomy_login_curl(username, password):
    '''    Logins to Atomy customer section    '''
    output = subprocess.run([
        '/usr/bin/curl',
        'https://www.atomy.kr/v2/Home/Account/Login',
        '--data-raw',
        f'src=&userId={username}&userPw={password}&idSave=on&rpage=',
        '-v'
        ],
        encoding='utf-8', stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=False)
    if re.search('< location: /V2', output.stderr):
        return re.findall('set-cookie: (.*)', output.stderr)
    return None

def atomy_login(username, password, browser=None, run_browser=True):
    if not run_browser:
        return _atomy_login_curl(username, password)
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

def get_document_from_url(url, headers=None, raw_data=None):
    # headers_list = [
    #     header for set in list(map(
    #         lambda h: ['-H', f"{h}: {headers[h]}"], headers)) for header in set
    # ]
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data = ['--data-raw', raw_data] if raw_data else None
    output = subprocess.run([
        '/usr/bin/curl',
        url,
        '-v'
        ] + headers_list + raw_data,
        encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    if re.search('HTTP.*? 200', output.stderr):
        doc = lxml.html.fromstring(output.stdout)
        return doc
    if 'Could not resolve host' in output.stderr:
        return get_document_from_url(url, headers, raw_data)
    if re.search('HTTP.* 302', output.stderr) and \
        re.search('location: /v2/Home/Account/Login', output.stderr):
        raise AtomyLoginError()

    raise Exception("Couldn't get page", output.stderr)
