import itertools
import json
import logging
import re
import subprocess
import threading
from time import sleep

import lxml.html
from flask import current_app

from app.tools import invoke_curl
from exceptions import AtomyLoginError, HTTPError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
try:
    logger = current_app.logger
except:
    pass

# class SessionManager:
#     __instance = None

#     @classmethod
#     def create_instance(cls, username, password):
#         cls.__instance = SessionManager(username, password)

#     @classmethod
#     def get_instance(cls):
#         return cls.__instance

#     def __init__(self, username, password):
#         self.__username = username
#         self.__password = password
#         self.__create_session()

#     def __create_session(self):
#         with threading.Lock():
#             self.__session = atomy_login(
#                 username=self.__username, password=self.__password, run_browser=False)

#     def get_document(self, url, raw_data=None, headers={}):
#         logger = logging.getLogger('SessionManager.get_document()')
#         attempts_left = 3
#         while attempts_left:
#             try:
#                 return get_document_from_url(url,
#                     headers=[{'Cookie': c} for c in self.__session] + \
#                             [{key: value} for key, value in headers.items()],
#                     raw_data=raw_data)
#             except AtomyLoginError:
#                 logger.info("Session expired. Logging in")
#                 self.__create_session()
#                 attempts_left -= 1
    
#     def get_json(self, url, raw_data=None, headers={}, method='get'):
#         _logger = logging.getLogger('SessionManager.get_json()')
#         attempts_left = 3
#         while attempts_left:
#             try:
#                 content = invoke_curl(url, method=method, raw_data=raw_data,
#                     headers=[{'Cookie': c} for c in self.__session] +
#                             [{key: value} for key, value in headers.items()] +
#                             [{"Content-type": "application/json"}]).output
#                 return json.loads(content)
#             except AtomyLoginError:
#                 _logger.info("Session expired. Logging in")
#                 self.__create_session()
#                 attempts_left -= 1
#         raise Exception("Couldn't get JSON document due to login issue")

def get_document_from_url(url, headers=None, raw_data=None):
    _logger = logger.getChild('get_document_from_url')
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data = ['--data-raw', raw_data] if raw_data else []
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
            _logger.warning("Couldn't resolve host name for %s. Will try in 30 seconds", url)
            sleep(30)
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

# def invoke_curl(url: str, raw_data: str=None, headers: list[dict[str, str]]=[],
#                 method='GET') -> tuple[str, str]:
#     '''Calls curl and returns its stdout and stderr'''
#     _logger = logging.root.getChild('invoke_curl')
#     headers_list = list(itertools.chain.from_iterable([
#         ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
#     ]))
#     raw_data_param = ['--data-raw', raw_data] if raw_data else []
#     if raw_data:
#         method = 'POST'
#     run_params = [ #type: ignore
#         '/usr/bin/curl',
#         url,
#         '-X', method,
#         '--socks5', 'localhost:9050',
#         '-v',
#         '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
#         ] + headers_list + raw_data_param
#     try:
#         output = subprocess.run(run_params,
#             encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
#         if 'Could not resolve host' in output.stderr or re.search(r'HTTP.*? 50\d', output.stderr):
#             _logger.warning("Server side error occurred. Will try in 30 seconds", url)
#             sleep(30)
#             return invoke_curl(url, raw_data, headers, method)
#         return output.stdout, output.stderr
#     except TypeError:
#         _logger.exception(run_params)
#         return '', ''

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
