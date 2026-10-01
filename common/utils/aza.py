'''Utilities for AtomyAza (atomyaza.co.kr)'''
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL_BASE = 'https://atomyaza.co.kr'
USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) ' \
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
TIMEOUT = 30

class AzaLoginError(Exception):
    '''Raised when login to AtomyAza fails or the session isn't authenticated'''

def normalize_member_id(member_id: str) -> str:
    '''Applies the same member ID normalization the site's login form does:
    numeric IDs shorter than 8 digits are prefixed with "S" and padded to 7 digits'''
    if member_id.isdigit() and len(member_id) < 8:
        return 'S' + member_id.zfill(7)
    return member_id

def create_session(socks5_proxy: str='') -> requests.Session:
    '''Creates an HTTP session with retries on connection errors and HTTP 5xx'''
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT, 'Referer': f'{URL_BASE}/m/'})
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504],
                  allowed_methods=['GET'])
    session.mount('https://', HTTPAdapter(max_retries=retry, pool_maxsize=10))
    if socks5_proxy:
        session.proxies = {
            'http': f'socks5h://{socks5_proxy}',
            'https': f'socks5h://{socks5_proxy}'
        }
    return session

def aza_login(username: str, password: str, socks5_proxy: str='',
              session: Optional[requests.Session]=None) -> requests.Session:
    '''Logs in to AtomyAza with Atomy member credentials.
    Returns the session holding authentication cookies'''
    if session is None:
        session = create_session(socks5_proxy)
    response = session.post(
        f'{URL_BASE}/m/bbs/atomy_post.php',
        data={
            'url': f'{URL_BASE}/m',
            'mb_id': normalize_member_id(username),
            'mb_password': password
        },
        headers={'X-Requested-With': 'XMLHttpRequest'},
        timeout=TIMEOUT)
    try:
        result = response.json()
    except ValueError as ex:
        raise AzaLoginError(
            f"Unexpected login response (HTTP {response.status_code})") from ex
    if str(result.get('code')) != '1':
        raise AzaLoginError(result.get('error') or 'Login failed')
    return session
