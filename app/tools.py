''' Handful tools '''
import enum
from datetime import datetime
from glob import glob
import itertools
import json
import logging
import subprocess
from functools import reduce
import os
import os.path
import re
from typing import T, Any, Callable # type: ignore
import lxml
from lxml import etree
from time import sleep
from werkzeug.datastructures import MultiDict

from flask import current_app

from exceptions import FilterError, HTTPError

from app.models.base import BaseModel

# logging.basicConfig(level=logging.INFO)

__app_abs_dir_name = os.path.abspath(os.path.dirname(__file__))

# def get_free_file_name(path):
#     dir_name = os.path.dirname(os.path.join(__app_abs_dir_name, path))
#     free_path = os.path.basename(path)
#     i = 0
#     while os.path.exists(os.path.join(dir_name, free_path)):
#         free_path = f"{os.path.basename(path)}-{i}"
#         i += 1
#     return os.path.join(os.path.dirname(path), free_path)
def get_tmp_file_by_id(file_id):
    files = glob(f'/tmp/*{file_id}*')
    if len(files) == 0:
        raise FileNotFoundError
    return files[0]

def rm(path, not_exist_raise=False):
    abspath = os.path.join(__app_abs_dir_name, path)
    try:
        os.remove(abspath)
    except Exception as e:
        if not_exist_raise:
            raise e

def write_to_file(path, data):
    abspath = os.path.join(__app_abs_dir_name, path[1:])
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    with open(abspath, 'wb') as file:
        file.write(data)
        file.close()

def prepare_datatables_query(query, args, filter_clause=None) -> tuple[Any, int, int]:
    logger = logging.getLogger('prepare_datatables_query')
    def get_column(query, column_name):
        try:
            return getattr(query.column_descriptions[0]['type'], column_name)
        except AttributeError:
            logger.debug("Couldn't get column %s from %s", column_name, query.column_descriptions[0]['type'])
            return column_name

    if not isinstance(args, MultiDict):
        raise AttributeError("Arguments aren't of MultiDict type")
    args = convert_datatables_args(args)
    columns = args.get('columns') or []
    records_total = query.count()
    query_filtered = query
    # Filtering .....
    target_model = query_filtered.column_descriptions[0]['entity']
    if isinstance(args['search']['value'], str) and args['search']['value'] != '':
        query_filtered = target_model.get_filter(query_filtered, None, args['search']['value'])
    for column_data in columns:
        if column_data['search']['value'] != '':
            column_name = column_data['name'] if column_data['name'] else column_data['data']
            column = get_column(query_filtered, column_name)
            if column_data['search']['value'] == 'NULL' and not isinstance(column, str):
                query_filtered = query_filtered.filter(column == None)
            else:
                try:
                    query_filtered = target_model \
                        .get_filter(query_filtered, column, column_data['search']['value'])
                except NotImplementedError:
                    try:
                        query_filtered = query_filtered.filter(
                            column.like('%' + column_data['search']['value'] + '%')) #type: ignore
                    except:
                        raise FilterError(f"Couldn't figure out how to filter the column '{column_name}' in the object {target_model}. Probably {target_model} has no get_filter() implemented or get_filter() doesn't filter by '{column_name}'")
    records_filtered = query_filtered.count()
    # Sorting
    for sort_column_input in args.get('order') or []:
        sort_column_name = columns[int(sort_column_input['column'])]['data']
        #logger.debug(sort_column_name)
        if sort_column_name != '':
            sort_column = get_column(query_filtered, sort_column_name)
            if sort_column_input['dir'] == 'desc':
                sort_column = sort_column.desc()
            query_filtered = query_filtered.order_by(sort_column)
    # Limiting to page
    if args.get('start') is not None and args.get('length') is not None:
        query_filtered = query_filtered.offset(args['start']) \
                                       .limit(args['length'])

    return (query_filtered, records_total, records_filtered)

def convert_datatables_args(raw_args):
    def set_value(args_dict, keys, value):
        if len(keys) == 1:
            if value == 'true': value = True
            if value == 'false': value = False
            args_dict[keys[0]] = value
        elif keys[0] == '':
            set_value(args_dict, keys[1:], value)
        else:
            if not args_dict.get(keys[0]):
                args_dict[keys[0]] = {}
            set_value(args_dict[keys[0]], keys[1:], value)
    def make_arrays(args_dict):
        for dict_item in args_dict.items():
            if isinstance(dict_item[1], dict):
                args_dict[dict_item[0]] = make_arrays(dict_item[1])
        
        keys_are_numbers = reduce(
            lambda acc, item: acc and re.match(r'^\d+$', item[0]) is not None,
            args_dict.keys(),
            True
        )
        if keys_are_numbers:
            args_dict = [item[1] for item in args_dict.items()]
        return args_dict
                

    args = {}
    for param in raw_args.items():
        keys = re.split(r'\[|\]', param[0])
        if len(keys) == 1:
            args[keys[0]] = param[1]
        else:
            set_value(args, keys[:-1], param[1])
    make_arrays(args)
    return args

def modify_object(entity: BaseModel, payload: dict[str, Any], 
                  editable_attributes: list[str]) -> BaseModel:
    for attr in editable_attributes:
        if payload.get(attr) is not None:
            if isinstance(getattr(entity, attr), enum.Enum):
                setattr(entity, attr, type(getattr(entity, attr))[payload[attr]]) # type: ignore
            else:
                try:
                    setattr(entity, attr, payload[attr])
                except Exception as ex:
                    raise type(ex)(attr, ex)
            entity.when_changed = datetime.now()
    return entity

def cleanse_payload(entity, payload):
    new_payload = {}
    for key, value in payload.items():
        try:
            attr = getattr(entity, key)
            if isinstance(attr, enum.Enum):
                if type(attr)[value] != attr:
                    new_payload[key] = value
            else:
                if type(attr)(value) != attr:
                    new_payload[key] = value
        except:
            new_payload[key] = value
    return new_payload

def stream_and_close(file_handle):
    yield from file_handle
    file_handle.close()


def invoke_curl(url: str, raw_data: str='', headers: list[dict[str, str]]=[],
                method='GET', use_proxy: bool=True, retries=2,
                ignore_ssl_check=False) -> tuple[str, str]:
    '''Calls curl and returns its stdout and stderr'''
    _logger = logging.root.getChild('invoke_curl')
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data_param = ['--data-raw', raw_data] if raw_data else []
    socks5_proxy_param = (
        ['--socks5', current_app.config.get('SOCKS5_PROXY')] #type: ignore
            if use_proxy and current_app.config.get('SOCKS5_PROXY') is not None else [])
    ignore_ssl_check_param = ['-k'] if ignore_ssl_check else []
    if raw_data:
        method = 'POST'
    run_params = [ #type: ignore
        '/usr/bin/curl',
        url,
        '-X', method,
        '-v',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        '--compressed' # need this for cases that response is zipped
        ] + headers_list + raw_data_param + socks5_proxy_param + ignore_ssl_check_param
    # _logger.info(' '.join(run_params))
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

    raise HTTPError(f"Couldn't get page {url}: {stderr}")

def get_html(url, raw_data: str='', headers: list=[], method='GET', retry=True, 
             get_data: Callable=invoke_curl, ignore_ssl_check=False
             ) -> etree.Element: #type: ignore
    stdout, stderr = get_data(url, raw_data, headers)
    if re.search('HTTP.*? 200', stderr) and len(stdout) > 0:
        doc = etree.fromstring(stdout, parser=etree.HTMLParser()) #type: ignore
        return doc

    raise HTTPError(f"Couldn't get page {url}: {stderr}")

def get_json(url, raw_data=None, headers: list=[], method='GET', retry=True, 
             get_data: Callable=invoke_curl, ignore_ssl_check=False
             ) -> dict[str, Any]:
    stdout, stderr = get_data(url, method=method, raw_data=raw_data,
        headers=headers + [{'Content-Type': 'application/json'}], 
        retries=3 if retry else 0, 
        ignore_ssl_check=ignore_ssl_check)
    try:
        return json.loads(stdout)
    except:
        if re.search('HTTP.*? 401', stderr):
            raise HTTPError(401)
        logging.exception("Couldn't get JSON out of response", stdout, stderr)
        raise Exception("Unknown error")

def try_perform(action:Callable, attempts:int=3, logger:logging.Logger=logging.root) -> Any:
    last_exception = None
    for _attempt in range(attempts):
        logger.debug("Running action %s. Attempt %s of %s", action, _attempt + 1, attempts)
        try:
            return action()
        except Exception as ex:
            logger.debug("During action %s an error has occurred: %s", action, ex)
            if not last_exception:
                last_exception = ex
            else:
                sleep(1)
    if last_exception:
        raise last_exception

def merge(a: dict, b: dict, path=None, force=False) -> dict:
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)], force=force)
            elif a[key] == b[key]:
                pass # same leaf value
            elif force:
                a[key] = b[key]
            else:
                raise Exception('Conflict at %s.  Values: (%s, %s)' % 
                    ('.'.join(path + [str(key)]), a[key], b[key]))
        else:
            a[key] = b[key]
    return a

def retryable(func:Callable, attempts:int=3) -> Callable:
    '''Calls a function. If it raises an exception it '''
    def wrapper(*args, **kwargs):
        __attempts = kwargs.get('__attempts') or attempts
        try:
            if kwargs.get('__attempts'): del kwargs['__attempts']
            if kwargs.get('__last_exc'): del kwargs['__last_exc']
            func(*args, **kwargs)
        except Exception as e:
            if __attempts > 1:
                kwargs['__last_exc'] = e
                kwargs['__attempts'] = __attempts - 1
                logging.exception("During calling %s an error has occurred %s", func, e)
                logging.error("Will retry %s more time%s", kwargs['__attempts'], 
                                's' if kwargs['__attempts'] > 1 else '')
                return wrapper(*args, **kwargs)
            else:
                raise e
    return wrapper

def first_or_default(list: list[T], filter: Callable[[T], bool], default: T=None) -> T:
    for item in list:
        if filter(item):
            return item
    return default
