import itertools
import json
import logging
import re
import subprocess
from time import sleep
from typing import Any, Callable
from xml.etree.ElementTree import fromstring

from requests import HTTPError

from exceptions import AtomyLoginError

def get_document_from_url(url, headers=[], raw_data: str=''):
    logger = logging.getLogger('utils.get_document_from_url')
    stdout, stderr = invoke_curl(url=url, headers=headers, raw_data=raw_data)
    try:
        if re.search('HTTP.*? (200|304)', stderr):
            cleaned_string = re.sub(
                u'[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\U00010000-\U0010FFFF]+',
                '', stdout)
            doc = fromstring(cleaned_string)
            return doc
        if 'Could not resolve host' in stderr:
            logger.warning("Couldn't resolve host name for %s. Will try in 30 seconds", url)
            sleep(30)
            return get_document_from_url(url, headers, raw_data)
        if re.search('HTTP.* 302', stderr) and \
            re.search('location: /v2/Home/Account/Login', stderr):
            raise AtomyLoginError()
        if re.search(r'HTTP.*? 50\d', stderr):
            logger.warning('Server has returned HTTP 50*. Will try in 30 seconds')
            sleep(30)
            return get_document_from_url(url, headers, raw_data)

        raise Exception("Couldn't get page", stderr)
    except TypeError:
        logger.exception(url, headers, raw_data)


def invoke_curl(url: str, raw_data: str='', headers=[],
                method='GET', retries=2, socks5_proxy:str='', ignore_ssl_check=False
                ):
    '''Calls curl and returns its stdout and stderr'''
    _logger = logging.root.getChild('invoke_curl')
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data_param = ['--data-raw', raw_data] if raw_data else []
    socks5_proxy_param = ['--socks5', socks5_proxy] if socks5_proxy else []
    ignore_ssl_check_param = ['-k'] if ignore_ssl_check else []
    if raw_data:
        method = 'POST'
    run_params = [ #type: ignore
        '/usr/bin/curl',
        url,
        '-X', method,
        # '--socks5', 'localhost:9050',
        '-v',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        ] + headers_list + raw_data_param + socks5_proxy_param + ignore_ssl_check_param
    
    try:
        output = subprocess.run(run_params,
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ('Could not resolve host' in output.stderr 
            or re.search(r'HTTP.*? 50\d', output.stderr)) and retries:
            _logger.warning("Server side error occurred. Will try in 30 seconds. (%s)", url)
            _logger.warning(output.stderr)
            sleep(30)
            return invoke_curl(url, raw_data, headers, method, retries=retries - 1)
        return output.stdout, output.stderr
    except TypeError:
        _logger.exception(run_params)
        return '', ''

    
def get_json(url, raw_data=None, headers=[], method='GET', retries=0, 
             get_data: Callable=invoke_curl, ignore_ssl_check=False,
             socks5_proxy=''
             ):
    stdout, stderr = get_data(url, method=method, raw_data=raw_data,
        headers=headers, retries=retries, 
        ignore_ssl_check=ignore_ssl_check, socks5_proxy=socks5_proxy)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        if re.search('HTTP.*? 401', stderr):
            raise HTTPError(401)
        if retries > 0:
            logging.warning("Couldn't get json from URL %s. Will retry %s more time%s",
                            url, retries, 's' if retries > 1 else '')
            return get_json(url, raw_data, headers, method, retries - 1, get_data,
                            ignore_ssl_check)
        logging.exception("Couldn't get JSON out of response")
        logging.error("STDOUT: %s", stdout)
        logging.error("STDERR: %s", stderr)
        raise Exception("Unknown error")

