import base64
import hashlib
import itertools
import json
import logging
import re
import subprocess
import tempfile
import time
from time import sleep
from typing import Any

from . import invoke_curl, get_json
from common.exceptions import AtomyLoginError, HTTPError

URL_BASE = 'https://kr.atomy.com'
URL_SUFFIX = '_siteId=kr&_deviceType=pc&locale=ko-KR'
URL_NETWORK_MANAGER = 'http://localhot:5001'

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
try:
    from flask import current_app
    logger = current_app.logger
except Exception:
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

def _curl_with_jar(url: str, jar_path: str, raw_data: str = '',
                   headers: list = [], socks5_proxy: str = ''):
    """Like invoke_curl but shares a cookie jar across calls."""
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k, v in pair.items()
    ]))
    raw_data_param = ['--data-raw', raw_data] if raw_data else []
    socks5_param = ['--socks5', socks5_proxy] if socks5_proxy else []
    method = 'POST' if raw_data else 'GET'
    run_params = [
        '/usr/bin/curl', url,
        '-X', method, '-v',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        '-c', jar_path,
        '-b', jar_path,
    ] + headers_list + raw_data_param + socks5_param
    logger.debug(' '.join(run_params))
    output = subprocess.run(run_params, encoding='utf-8',
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return output.stdout, output.stderr


def _solve_altcha(stdout: str) -> tuple:
    """Parse challenge JSON and brute-force the ALTCHA nonce.
    :returns: (payload_b64, took_ms)"""
    data = json.loads(stdout)
    challenge  = data["challenge"]
    signature  = data["signature"]
    algorithm  = data["algorithm"]
    salt       = data["salt"]
    max_number = int(data["maxNumber"])

    start = time.monotonic()
    for i in range(max_number + 1):
        digest = hashlib.sha256(f"{salt}{i}".encode()).hexdigest()
        if digest == challenge:
            took = int((time.monotonic() - start) * 1000)
            payload = {
                "algorithm": algorithm,
                "challenge": challenge,
                "number": i,
                "salt": salt,
                "signature": signature,
                "took": took,
            }
            pay_load = base64.b64encode(
                json.dumps(payload, separators=(",", ":")).encode()
            ).decode()
            return pay_load, took
    raise AtomyLoginError(message="ALTCHA challenge could not be solved")


def atomy_login2(username, password, socks5_proxy="") -> str:
    '''Logs in to Atomy using new authentication interface
    :param username: user name
    :param password: password
     param socks5_proxy: address for socks5 proxy if needed
    :returns: JWT token'''
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=True) as jar_file:
        jar_path = jar_file.name

    challenge_start = time.monotonic()
    stdout, _ = _curl_with_jar(
        url=f'{URL_BASE}/login/challenge',
        jar_path=jar_path,
        socks5_proxy=socks5_proxy,
    )
    pay_load, _ = _solve_altcha(stdout)
    verify_operate_time = int((time.monotonic() - challenge_start) * 1000)

    stdout, stderr = _curl_with_jar(
        url=f'{URL_BASE}/login/doLogin',
        jar_path=jar_path,
        headers=[{"content-type": "application/json"}],
        raw_data=json.dumps({
            "mbrLoginId": username,
            "pwd": password,
            "saveId": False,
            "autoLogin": False,
            "recaptcha": "",
            "payLoad": pay_load,
            "verifyOperateTime": verify_operate_time,
        }),
        socks5_proxy=socks5_proxy,
    )
    if re.search('HTTP.*200', stderr) is  None:
        logger.debug("Couldn't log in to Atomy.")
        logger.debug("STDERR: %s", stderr)
        logger.debug("STDOUT: %s", stdout)
        raise AtomyLoginError(username)
    result = json.loads(stdout)
    if result.get('code') != '0000':
        raise AtomyLoginError(username=username, password=password,
                              message=result.get('message'))

    logger.info(f"Logged in successfully as {username}")
    # JSESSIONID may have been set during the challenge call and stored in the jar,
    # so read it from the jar file rather than from doLogin response headers.
    try:
        with open(jar_path) as f:
            jar_contents = f.read()
        match = re.search(r'\bJSESSIONID\b\s+(\S+)', jar_contents)
        if match:
            return f"JSESSIONID={match.group(1)}"
    except OSError:
        pass
    # Fallback: try response headers (original behaviour)
    jwt = re.search(r'set-cookie: (JSESSIONID=.*?);', stderr).group(1)  # type: ignore
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
