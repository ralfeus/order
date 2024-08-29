import json
import logging
import re
import threading
from time import sleep
from typing import Any
from urllib.parse import urlencode

from flask import current_app

from . import invoke_curl
from exceptions import AtomyLoginError, HTTPError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
try:
    logger = current_app.logger
except:
    pass

class SessionManager:
    __instance = None

    @classmethod
    def create_instance(cls, username, password):
        cls.__instance = SessionManager(username, password)

    @classmethod
    def get_instance(cls):
        return cls.__instance

    def __init__(self, username, password):
        self.__username = username
        self.__password = password
        self.__create_session()

    def __create_session(self):
        with threading.Lock():
            self.__session = atomy_login(
                username=self.__username, password=self.__password, run_browser=False)

def _atomy_login_curl(username, password) -> list[str]:
    '''    Logins to Atomy customer section    
    Returns list of session cookies
    '''
    if len(username) < 8:
        username = 'S' + username
    stdout, stderr = invoke_curl(
        url='https://www.atomy.kr/v2/Home/Account/Login',
        raw_data=urlencode({
            'userId': username,
            'userPw': password,
            'orderNum': '',
            'userName': '',
            'idSave': 'on',
            'rpage': '',
            'loadPage': ''
        })
    )
    if re.search('< location: /[vV]2', stderr) or \
       re.search('btnChangePassword', stdout):
        return re.findall('set-cookie: (.*)', stderr)
    elif re.search("var isLoginFail = \\'True\\';", stdout):
        message = re.search(r"isLoginFail ==.*\n.*?alert\('(.*?)'", stdout, re.MULTILINE).groups()[0]
        raise AtomyLoginError(username=username, message=message)
    elif re.search("HTTP.*503", stderr):
        message = "Vendor's server is temporary unavailable. Please try again later"
        raise AtomyLoginError(username=username, message=message)

    raise HTTPError((stdout, stderr))

def atomy_login(username, password, browser=None, run_browser=False) -> list[str]:
    if not run_browser:
        return try_perform(lambda: _atomy_login_curl(username, password))
    raise NotImplementedError("Browser login is not implemented")

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

URL_BASE = 'https://shop-api.atomy.com/svc'
URL_SUFFIX = '_siteId=kr&_deviceType=pc&locale=ko-KR'
def atomy_login2(username, password, socks5_proxy=""):
    '''Logs in to Atomy using new authentication interface
    :param username: user name
    :param password: password
     param socks5_proxy: address for socks5 proxy if needed
    :returns: JWT token'''
    URL_BASE = 'https://shop-api.atomy.com/svc'
    jwt = __get_token(socks5_proxy)
    stdout, stderr = invoke_curl(
        url=f'{URL_BASE}/signIn?_siteId=kr',
        headers=[{'Cookie': jwt}],
        raw_data=urlencode({
            'id': username, 
            'password': password
        }),
        socks5_proxy=socks5_proxy
    )
    result = json.loads(stdout)
    if result['result'] == '200':
        logger.info(f"Logged in successfully as {username}")
        jwt = re.search('set-cookie: (atomySvcJWT=.*?);', stderr).group(1)
        return jwt
    else:
        raise AtomyLoginError(username)

def __get_token(socks5_proxy=""):
    _, stderr = invoke_curl(
        url='https://shop-api.atomy.com/auth/svc/jwt?_siteId=kr',
        socks5_proxy=socks5_proxy
    )
    token_match = re.search("set-cookie: (atomySvcJWT=.*?);", stderr)
    if token_match is not None:
        return token_match.group(1)
    else:
        raise Exception("Could not get token. The problem is at Atomy side")
