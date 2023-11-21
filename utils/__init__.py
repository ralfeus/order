import itertools
import logging
import re
import subprocess
from time import sleep

import lxml
import lxml.html

from exceptions import AtomyLoginError

def get_document_from_url(url, headers=None, raw_data=None):
    logger = logging.getLogger('utils.get_document_from_url')
    stdout, stderr = invoke_curl(url=url, headers=headers, raw_data=raw_data)
    try:
        if re.search('HTTP.*? (200|304)', stderr):
            doc = lxml.html.fromstring(stdout)
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


def invoke_curl(url: str, raw_data: str='', headers: list[dict[str, str]]=[],
                method='GET', retry=True, socks5_proxy:str='') -> tuple[str, str]:
    '''Calls curl and returns its stdout and stderr'''
    _logger = logging.root.getChild('invoke_curl')
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data_param = ['--data-raw', raw_data] if raw_data else []
    socks5_proxy_param = ['--socks5', socks5_proxy] if socks5_proxy else []
    if raw_data:
        method = 'POST'
    run_params = [ #type: ignore
        '/usr/bin/curl',
        url,
        '-X', method,
        # '--socks5', 'localhost:9050',
        '-v',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        ] + headers_list + raw_data_param + socks5_proxy_param
    try:
        output = subprocess.run(run_params,
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ('Could not resolve host' in output.stderr 
            or re.search(r'HTTP.*? 50\d', output.stderr)) and retry:
            _logger.warning("Server side error occurred. Will try in 30 seconds", url)
            sleep(30)
            return invoke_curl(url, raw_data, headers, method)
        return output.stdout, output.stderr
    except TypeError:
        _logger.exception(run_params)
        return '', ''