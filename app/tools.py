''' Handful tools '''
from datetime import datetime
import logging
from logging import Logger
import os
import os.path
import re
from subprocess import Popen, PIPE
import sys
from time import sleep
from werkzeug.datastructures import MultiDict

from sqlalchemy import or_

logging.basicConfig(level=logging.INFO)

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

def start_job(job, logger: Logger = None):
    if not logger:
        logger = logging.getLogger('job')
        logger.setLevel(logging.INFO)
    # do the UNIX double-fork magic, see Stevens' "Advanced 
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    logger.info('Starting job %s', job)
    try:
        pid = os.fork()
        if pid > 0:
            # parent process, return and keep running
            return pid
    except OSError as ex:
        logger.error("fork #1 failed: %d (%s)", ex.errno, ex.strerror)
        sys.exit(1)

    # os.setsid()

    # # do second fork
    # try: 
    #     pid = os.fork() 
    #     if pid > 0:
    #         # exit from second parent
    #         sys.exit(0) 
    # except OSError as e: 
    #     print("fork #2 failed: %d (%s)" % (e.errno, e.strerror))
    #     sys.exit(1)

    # do stuff

    job_path = os.path.realpath(f'jobs/{job}.py')
    logger.info(job_path)
    if os.path.exists(job_path):
        env = os.environ
        env['PYTHONPATH'] = os.getcwd()
        proc = Popen(['python3', job_path], env=env, stdout=PIPE, stderr=PIPE)
        logger.info(proc.pid)
        # stdout_iter = iter(proc.stdout.readline, b'')
        # stderr_iter = iter(proc.stderr.readline, b'')
        while proc.poll() is None:
            # logger.info(datetime.now())
            try:
                for line in proc.stdout:
                    logger.info(line.decode('utf-8'))
                for line in proc.stderr:
                    logger.warning(line.decode('utf-8'))
                sleep(1)
            except:
                logger.exception('Problem')
        logger.info("Finished")
    else:
        logger.error(f"Can't find job {job}. Ensure the file {job_path} exists")

    # all done
    sys.exit(os.EX_OK)

def start_job_func(job, logger: Logger = None):
    if not logger:
        logger = logging.getLogger('job')
        logger.setLevel(logging.INFO)
    else:
        logger = logger.getChild('job')
    # do the UNIX double-fork magic, see Stevens' "Advanced 
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    try:
        pid = os.fork()
        if pid > 0:
            # parent process, return and keep running
            logger.info("Child PID is %d", pid)
            return pid
    except OSError as ex:
        logger.error("fork #1 failed: %d (%s)", ex.errno, ex.strerror)
        sys.exit(1)

    logger.info('Starting function %s as job', job.__name__)
    job(logger)
    logger.info("Finishing job %d", os.getpid())
    sys.exit(os.EX_OK)
