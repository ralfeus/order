import json
import logging
import re
from typing import Optional

from tools import invoke_curl

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

URL_BASE = 'https://kr.atomy.com'
URL_SUFFIX = '_siteId=kr&_deviceType=pc&locale=ko-KR'

class AtomyLoginError(Exception):
    def __init__(self, username=None, password=None, message=None):
        super().__init__()
        self.username = username
        self.password = password
        self.message = message
        self.args = (username, message)

    def __str__(self):
        return f"Couldn't log in as '{self.username}':'{self.password}': {self.message}"


def atomy_login2(username, password, socks5_proxy:Optional[str]=None) -> str:
    '''Logs in to Atomy using new authentication interface

    :param username: user name
    :param password: password
     param socks5_proxy: address for socks5 proxy if needed
    :returns: JWT token'''
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

def set_language(language_code: str, session: str, socks5_proxy:Optional[str]=None
                 ) -> tuple[str, str]:
    '''Sets language for Atomy session

    :param language_code: language code to set: ['ko', 'en']
    :param socks5_proxy: address for socks5 proxy if needed
    '''
    url = f"{URL_BASE}/common/setCookieLanguage"
    return invoke_curl(
        url=url,
        method='POST',
        headers=[{"content-type": "application/x-www-form-urlencoded"}, {"Cookie": session}],
        raw_data=f"lang={language_code}",
        socks5_proxy=socks5_proxy
    )