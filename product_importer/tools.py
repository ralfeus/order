''' Handful tools '''
import itertools
import json
import logging
import subprocess
import re
import lxml
from lxml import etree #type:ignore
from time import sleep
from typing import Any, Callable, Optional

# logging.basicConfig(level=logging.INFO)

def invoke_curl(url: str, raw_data: str='', headers: list[dict[str, str]]=[],
                method='GET', socks5_proxy:Optional[str]=None, retries=2,
                ignore_ssl_check=False) -> tuple[str, str]:
    '''Calls curl and returns its stdout and stderr'''
    _logger = logging.root.getChild('invoke_curl')
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data_param = ['--data-raw', raw_data] if raw_data else []
    socks5_proxy_param = (
        ['--socks5', socks5_proxy] #type: ignore
            if socks5_proxy is not None else [])
    ignore_ssl_check_param = ['-k'] if ignore_ssl_check else []
    if raw_data and method == 'GET':
        method = 'POST'
    run_params = [ #type: ignore
        '/usr/bin/curl',
        url,
        '-X', method,
        '-v',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        '--compressed' # need this for cases that response is zipped
        ] + headers_list + raw_data_param + socks5_proxy_param + ignore_ssl_check_param
    _logger.debug(' '.join(run_params))
    try:
        output = subprocess.run(run_params,
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ('Could not resolve host' in output.stderr 
            or re.search(r'HTTP.*? 50\d', output.stderr)) and retries:
            _logger.warning("Server side error occurred. Will try in 30 seconds (%s)", url)
            _logger.warning(output.stderr)
            sleep(30)
            return invoke_curl(url, raw_data, headers, method, retries=retries - 1)
        return output.stdout, output.stderr
    except TypeError:
        _logger.exception(run_params)
        return '', ''

def get_document_from_url(url: str, headers: dict[str, str]={}, raw_data: str='',
        encoding: str='utf-8', resolve: str=''):
    stdout, stderr = invoke_curl(url, raw_data, [{k: v} for k, v in headers.items()])

    if re.search('HTTP.*? 200', stderr) and len(stdout) > 0:
        doc = lxml.html.fromstring(stdout) #type: ignore
        return doc

    raise Exception(f"Couldn't get page {url}: {stderr}")

def get_html(url, raw_data: str='', headers: list=[], method='GET', retry=True, 
             get_data: Callable=invoke_curl, ignore_ssl_check=False
             ) -> etree.Element: #type: ignore
    stdout, stderr = get_data(url, raw_data, headers)
    if re.search('HTTP.*? 200', stderr) and len(stdout) > 0:
        doc = etree.fromstring(stdout, parser=etree.HTMLParser()) #type: ignore
        return doc

    raise Exception(f"Couldn't get page {url}: {stderr}")

def get_json(url, raw_data=None, headers: list=[], method='GET', retry=True, 
             get_data: Callable=invoke_curl, ignore_ssl_check=False
             ) -> dict[str, Any] | list[Any]:
    content_type = [h for h in headers if list(h.keys())[0].lower() == 'content-type']
    stdout, stderr = get_data(url, method=method, raw_data=raw_data,
        headers=headers + ([{'Content-Type': 'application/json'}]
                           if len(content_type) == 0 else []), 
        retries=3 if retry else 0, 
        ignore_ssl_check=ignore_ssl_check)
    try:
        return json.loads(stdout)
    except:
        if re.search('HTTP.*? 401', stderr):
            raise Exception("HTTP 401 Unauthorized")
        logging.exception("Couldn't get JSON out of response")
        logging.exception(stdout)
        logging.exception(stderr)
        raise Exception("Unknown error")
