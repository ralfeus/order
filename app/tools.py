''' Handful tools '''
import enum
from datetime import datetime
from glob import glob
from flask import current_app, send_file
from functools import reduce
import logging
import os
import os.path
import re
from werkzeug.datastructures import MultiDict


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

def prepare_datatables_query(query, args, filter_clause):
    def get_column(query, column_name):
        try:
            return getattr(query.column_descriptions[0]['type'], column_name)
        except AttributeError:
            return column_name

    if not isinstance(args, MultiDict):
        raise AttributeError("Arguments aren't of MultiDict type")
    args = convert_datatables_args(args)
    columns = args['columns']
    records_total = query.count()
    query_filtered = query
    # Filtering .....
    if isinstance(args['search']['value'], str) and args['search']['value'] != '':
        query_filtered = query.filter(filter_clause)
    else:
        for column_data in columns:
            if column_data['search']['value'] != '':
                column = get_column(
                    query_filtered, 
                    column_data['name'] if column_data['name'] else column_data['data'])
                try:
                    target_model = query_filtered.column_descriptions[0]['entity']
                    query_filtered = target_model \
                        .get_filter(query_filtered, column, column_data['search']['value'])
                except NotImplementedError:
                    query_filtered = query_filtered.filter(
                        get_column(query_filtered, column_data['data'])
                            .like('%' + column_data['search']['value'] + '%'))
    records_filtered = query_filtered.count()
    # Sorting
    for sort_column_input in args['order']:
        sort_column_name = columns[int(sort_column_input['column'])]['data']
        if sort_column_name != '':
            sort_column = get_column(query_filtered, sort_column_name)
            if sort_column_input['dir'] == 'desc':
                sort_column = sort_column.desc()
            query_filtered = query_filtered.order_by(sort_column)
    # Limiting to page
    query_filtered = query_filtered.offset(args['start']). \
                                           limit(args['length'])

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

def modify_object(entity, payload, editable_attributes):
    for attr in editable_attributes:
        if payload.get(attr) is not None:
            if isinstance(getattr(entity, attr), enum.Enum):
                setattr(entity, attr, type(getattr(entity, attr))[payload[attr]])
            else:
                try:
                    setattr(entity, attr, payload[attr])
                except Exception as ex:
                    raise type(ex)(attr, ex)
            entity.when_changed = datetime.now()
    return entity

def stream_and_close(file_handle):
    yield from file_handle
    file_handle.close()
