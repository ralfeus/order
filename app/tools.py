''' Handful tools '''
import os
import os.path
import re
from werkzeug.datastructures import MultiDict

from sqlalchemy import or_

__app_abs_dir_name = os.path.abspath(os.path.dirname(__file__))

# def get_free_file_name(path):
#     dir_name = os.path.dirname(os.path.join(__app_abs_dir_name, path))
#     free_path = os.path.basename(path)
#     i = 0
#     while os.path.exists(os.path.join(dir_name, free_path)):
#         free_path = f"{os.path.basename(path)}-{i}"
#         i += 1
#     return os.path.join(os.path.dirname(path), free_path)

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
    if not isinstance(args, MultiDict):
        raise AttributeError("Arguments aren't of MultiDict type")
    args = convert_datatables_args(args)
    records_total = query.count()
    # Filtering .....
    if isinstance(args['search[value]'], str) and args['search[value]'] != '':
        query = query.filter(filter_clause)
    records_filtered = query.count()
    # Sorting
    columns = args['columns']
    sort_column_input = args['order']['0']
    sort_column_name = columns[sort_column_input['column']]['data']
    if sort_column_name != '':
        sort_column = query.column_descriptions[0]['expr'].columns[sort_column_name]
        if sort_column_input['dir'] == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    # Limiting to page
    query = query.offset(args['start']). \
                  limit(args['length'])

    return (query, records_total, records_filtered)

def convert_datatables_args(raw_args):
    args = {}
    for param in raw_args.items():
        match = re.search(r'(\w+)\[(\d+)\]\[(\w+)\]', param[0])
        if match:
            (array, index, attr) = match.groups()
            if not args.get(array):
                args[array] = {}
            if not args[array].get(index):
                args[array][index] = {}
            args[array][index][attr] = param[1]
        else:
            args[param[0]] = param[1]
    return args