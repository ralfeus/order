'''
Contains client routes of the application
'''
from glob import glob
import logging
import os, os.path
from flask import Blueprint, abort, current_app, redirect, \
    send_from_directory, send_file
from flask_security import login_required, roles_required, current_user

client = Blueprint('client', __name__, url_prefix='/')


@client.route('/')
@login_required
def index():
    '''
    Entry point to the application.
    Takes no arguments
    '''
    if current_user.has_role('admin'):
        return redirect('/admin/orders')
    else:
        return redirect('/orders')

@client.route('/admin')
@login_required
@roles_required('admin')
def admin_dashboard():
    '''
    Shows admin dashboard
    Currently it's a list of ordes
    '''
    return redirect('orders')


@client.route('/favicon.ico')
def favicon():
    return send_from_directory('static/images', 'favicon.ico')

@client.route('/upload/<path:path>')
@login_required
def send_from_upload(path):
    # logger = logging.getLogger(f'{__file__}:send_from upload()')
    # Must use os.getcwd() because it refers to tenant's home folder
    # app.root_path refers to application root, which is common for all tenants
    file = os.path.join(os.getcwd(), 
                        current_app.config['UPLOAD_PATH'], path)
    try:
        return send_file(file)
    except FileNotFoundError:
        logging.warning("Couldn't find file <%s>", file)
        abort(404)

@client.route('/upload/tmp/<file_id>')
@login_required
def get_tmp_file(file_id):
    files = glob(f'/tmp/{file_id}*')
    if len(files) == 0:
        abort(404)
    return send_file(files[0])

@client.route('/test', defaults={'task_id': None})
@client.route('/test/<task_id>')
def test(task_id):
    from app import celery
    result = None
    if task_id is None:
        from app.jobs import add_together
        result = {'result': add_together.delay(2, 3).id}
    else:
        task = celery.AsyncResult(task_id)
        result = {'state': task.state}
        if task.ready():
            result['result'] = task.result

    from flask import jsonify
    
    return jsonify(result)

@client.route('/cache')
def get_cache():
    from app import cache
    return cache.get_dict(), 200