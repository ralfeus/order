import itertools
import json
import logging
import re
import subprocess
import threading
from time import sleep
from urllib.parse import urlencode

from flask import current_app

from . import invoke_curl, get_document_from_url
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

    # def get_document(self, url, raw_data=None, headers={}):
    #     logger = logging.getLogger('SessionManager.get_document()')
    #     attempts_left = 3
    #     while attempts_left:
    #         try:
    #             return get_document_from_url(url,
    #                 headers=[{'Cookie': c} for c in self.__session] + \
    #                         [{key: value} for key, value in headers.items()],
    #                 raw_data=raw_data)
    #         except AtomyLoginError:
    #             logger.info("Session expired. Logging in")
    #             self.__create_session()
    #             attempts_left -= 1
    
    def get_json(self, url, raw_data=None, headers={}, method='get'):
        _logger = logging.getLogger('SessionManager.get_json()')
        attempts_left = 3
        while attempts_left:
            try:
                content = invoke_curl(url, method=method, raw_data=raw_data,
                    headers=[{'Cookie': c} for c in self.__session] +
                            [{key: value} for key, value in headers.items()] +
                            [{"Content-type": "application/json"}]).output
                return json.loads(content)
            except AtomyLoginError:
                _logger.info("Session expired. Logging in")
                self.__create_session()
                attempts_left -= 1
        raise "Couldn't get JSON document due to login issue"

def _atomy_login_curl(username, password):
    '''    Logins to Atomy customer section    '''
    if len(username) < 8:
        username = 'S' + username
    output = subprocess.run([
        '/usr/bin/curl',
        'https://www.atomy.kr/v2/Home/Account/Login',
        # '--resolve', 'www.atomy.kr:443:13.209.185.92,3.39.241.190',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        '--data-raw',
        urlencode({
            'userId': username,
            'userPw': password,
            'orderNum': '',
            'userName': '',
            'idSave': 'on',
            'rpage': '',
            'loadPage': ''
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
    elif re.search("HTTP.*503", output.stderr):
        message = "Vendor's server is temporary unavailable. Please try again later"
        raise AtomyLoginError(username=username, message=message)

    raise HTTPError(output)

def atomy_login(username, password, browser=None, run_browser=False):
    if not run_browser:
        return try_perform(lambda: _atomy_login_curl(username, password))
    raise "Browser login is not implemented"

def try_perform(action, attempts=3, logger=logging.RootLogger(logging.DEBUG)):
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
def atomy_login2(username, password):
    '''Logs in to Atomy using new authentication interface
    :param username: user name
    :param password: password
    :returns: JWT token'''
    URL_BASE = 'https://shop-api.atomy.com/svc'
    jwt = __get_token()
    stdout, stderr = invoke_curl(
        url=f'{URL_BASE}/signIn?_siteId=kr',
        headers=[{'Cookie': jwt}],
        raw_data=urlencode({
            'id': username, 
            'password': password
        })
    )
    result = json.loads(stdout)
    if result['result'] == '200':
        logger.info(f"Logged in successfully as {username}")
        jwt = re.search('set-cookie: (atomySvcJWT=.*?);', stderr).group(1)
        return jwt
    else:
        raise AtomyLoginError(username)

def __get_token():
    _, stderr = invoke_curl(
        url='https://shop-api.atomy.com/auth/svc/jwt?_siteId=kr'
    )
    token_match = re.search("set-cookie: (atomySvcJWT=.*?);", stderr)
    if token_match is not None:
        return token_match.group(1)
    else:
        raise Exception("Could not get token. The problem is at Atomy side")