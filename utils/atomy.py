import json
import logging
import re
from time import sleep
from typing import Any

from flask import current_app

from . import invoke_curl, get_json
from exceptions import AtomyLoginError, HTTPError

URL_BASE = 'https://kr.atomy.com'
URL_SUFFIX = '_siteId=kr&_deviceType=pc&locale=ko-KR'
URL_NETWORK_MANAGER = 'http://localhot:5001'

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
try:
    logger = current_app.logger
except:
    pass

#TODO: remove and replace with app.tools.try_perform
def try_perform(action, attempts=3, logger=logging.RootLogger(logging.DEBUG)) -> Any:
    last_exception = None
    for _attempt in range(attempts):
        logger.debug("Running action %s. Attempt %s of %s", action, _attempt + 1, attempts)
        try:
            return action()
        except Exception as ex:
            logger.warning("During action %s an error has occurred: %s", action, str(ex))
            if not last_exception:
                last_exception = ex
            else:
                sleep(1)
    if last_exception:
        raise last_exception

def atomy_login2(username, password, socks5_proxy="") -> str:
    '''Logs in to Atomy using new authentication interface
    :param username: user name
    :param password: password
     param socks5_proxy: address for socks5 proxy if needed
    :returns: JWT token'''
    # jwt = __get_token(socks5_proxy)
    stdout, stderr = invoke_curl(
        url=f'{URL_BASE}/login/doLogin',
        headers=[{"content-type": "application/json"}],
        raw_data=json.dumps({
            "mbrLoginId": username,
            "pwd": password,
            "saveId": False,
            "autoLogin": False,
            "recaptcha": "",
        }),
        socks5_proxy=socks5_proxy
    )
    if re.search('HTTP.*200', stderr) is  None:
        raise AtomyLoginError(username)
    result = json.loads(stdout)
    if result.get('code') != '0000':
        raise AtomyLoginError(username=username, password=password, 
                              message=result.get('message'))
    
    logger.info(f"Logged in successfully as {username}")
    jwt = re.search('set-cookie: (JSESSIONID=.*?);', stderr).group(1) # type: ignore
    return jwt

def get_bu_place_from_network(username) -> str:
    result = get_json(
        url=f"{URL_NETWORK_MANAGER}/api/v1/node/{username}",
        get_data=lambda url, method, raw_data, headers, retries, ignore_ssl_check: 
            invoke_curl(url, raw_data, headers, method, False, retries, ignore_ssl_check),)
    return result['center_code']
    
def get_bu_place_from_page(username, password) -> str:
    """Gets buPlace from the page. If not found, raises an exception.

    :param str username: Atomy user name
    :param str password: Atomy user password
    :returns str: buPlace code
    :raises AtomyLoginError: if login fails
    :raises Exception: if buPlace is not found in the page"""

    logger = logging.getLogger("get_bu_place_from_page")
    jwt = atomy_login2(username, password)
    logger.debug("Logged in successfully as %s", username)
    cart = get_json(
        url=f"{URL_BASE}/cart/registCart/30",
        headers=[
            {"Cookie": jwt}],
        raw_data="[]",
    )
    document, _ = invoke_curl(
        url=f"{URL_BASE}/order/sheet",
        headers=[
            {"Cookie": jwt},
            {"referer": f"{URL_BASE}/order/sheet"}],
        retries=0
    )
    bu_code_definition = re.search(r'buPlace.*?:.*?"(.*?)\\"', document) or \
        re.search(r'buCode.*?:.*?"(.*?)\\"', document)
    if bu_code_definition:
        return bu_code_definition.group(1)
    logger.info("Couldn't find buPlace in the page for user %s", username)
    try:
        message = json.loads(document)['errorMessage'] #type: ignore
    except:
        message = "Couldn't get buPlace from Atomy server."
    raise Exception(message)
    
