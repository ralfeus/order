import itertools
import json
import logging
import re
import subprocess
import threading
from time import sleep

import lxml.html
from flask import current_app

from exceptions import AtomyLoginError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
try:
    logger = current_app.logger
except:
    pass

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


#TODO: remove and replace with app.tools.try_perform
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
