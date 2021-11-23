import itertools
import logging
import re
import subprocess
from time import sleep
from urllib.parse import urlencode

import lxml.html
from flask import current_app

from selenium.common.exceptions import NoAlertPresentException, \
    NoSuchElementException, UnexpectedAlertPresentException

from exceptions import AtomyLoginError, HTTPError
# from app.utils.browser import Browser

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
try:
    logger = current_app.logger
except:
    pass

def _atomy_login_curl(username, password):
    '''    Logins to Atomy customer section    '''
    if len(username) < 8:
        username = 'S' + username
    output = subprocess.run([
        '/usr/bin/curl',
        'https://www.atomy.kr/v2/Home/Account/Login',
        '--data-raw',
        urlencode({
            'src': '',
            'userId': username,
            'userPw': password,
            'idSave': 'on',
            'rpage': ''
        }),
        '-v'
        ],
        encoding='utf-8', stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=False)
    if re.search('< location: /[vV]2', output.stderr) or \
       re.search('btnChangePassword', output.stdout):
        return re.findall('set-cookie: (.*)', output.stderr)
    elif re.search("var isLoginFail = \\'True\\';", output.stdout):
        message = re.search(r"isLoginFail ==.*\n.*?alert\('(.*?)'", output.stdout, re.MULTILINE).groups()[0]
        raise AtomyLoginError(username=username, message=message)

    raise HTTPError(output)

def atomy_login(username, password, browser=None, run_browser=False):
    if not run_browser:
        return _atomy_login_curl(username, password)
    raise "Browser login is not implemented"
    # _logger = logger.getChild('atomy_login')
    # local_browser = None
    # if browser:
    #     local_browser = browser
    # else:
    #     local_browser = Browser(config=current_app.config)
    # _logger.debug("Getting loging page")
    # local_browser.get('https://www.atomy.kr/v2/Home/Account/Login')
    # try:
    #     _logger.debug("Dismissing any alerts")
    #     local_browser.switch_to_alert().dismiss()
    # except NoAlertPresentException:
    #     pass
    # user_field = local_browser.get_element_by_id('userId')
    # password_field = local_browser.get_element_by_id('userPw')
    # user_field.send_keys(username)
    # password_field.send_keys(password)
    # _logger.debug("Submitting credentials")
    # password_field.submit()
    # try:
    #     _logger.debug("Waiting for home page")
    #     local_browser.wait_for_url('https://www.atomy.kr/v2/Home')
    #     _logger.debug('Login is successful')
    #     return
    # except UnexpectedAlertPresentException as ex:
    #     _logger.debug("Alert is %s. Login is failed", ex.args)
    #     raise AtomyLoginError(ex.args[0])
    # except Exception as ex:
    #     _logger.debug("Couldn't get home page")
    #     try:
    #         if local_browser.get_element_by_id('btnRelayPassword'):
    #             _logger.debug("Password change request is found. Dismissing")
    #             __ignore_change_password(local_browser)
    #         else:
    #             _logger.debug("The reason is unknown. Login is failed")
    #             raise AtomyLoginError(ex)
    #     except AtomyLoginError as ex:
    #         _logger.debug('Login is failed: %s', ex.args)
    #         raise ex
    #     except NoSuchElementException:
    #         _logger.debug("No password change request is found. Login is failed")
    #         raise AtomyLoginError()
    # finally:
    #     if not browser:
    #         local_browser.quit()

def __ignore_change_password(browser):
    try:
        browser.get_element_by_id('btnRelayPassword').click()
    except:
        AtomyLoginError("Couldn't ignore change password")

def get_document_from_url(url, headers=None, raw_data=None):
    _logger = logger.getChild('get_document_from_url')
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data = ['--data-raw', raw_data] if raw_data else None
    run_params = [
        '/usr/bin/curl',
        url,
        '-v'
        ] + headers_list + raw_data
    try:
        output = subprocess.run(run_params,
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

        if re.search('HTTP.*? (200|304)', output.stderr):
            doc = lxml.html.fromstring(output.stdout)
            return doc
        if 'Could not resolve host' in output.stderr:
            return get_document_from_url(url, headers, raw_data)
        if re.search('HTTP.* 302', output.stderr) and \
            re.search('location: /v2/Home/Account/Login', output.stderr):
            raise AtomyLoginError()
        if re.search(r'HTTP.*? 50\d', output.stderr):
            _logger.warning('Server has returned HTTP 50*. Will try in 30 seconds')
            sleep(30)
            return get_document_from_url(url, headers, raw_data)

        raise Exception("Couldn't get page", output.stderr)
    except TypeError:
        _logger.exception(run_params)
