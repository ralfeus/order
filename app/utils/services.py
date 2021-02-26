import os
from celery import Celery

def get_celery(app_name, job_modules=[]):
    queue_server = os.environ.get('OM_QUEUE_SERVER') or '127.0.0.1'
    celery = Celery(
        app_name,
        broker=f'pyamqp://{queue_server}',
        backend='rpc://',
        include=job_modules
    )
    celery.conf.update({
        'worker_hijack_root_logger': False
    })
    # celery.conf.add_defaults(flask_app.config)
    return celery

def init_celery(celery, flask_app):
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    # celery.config_from_object(flask_app.config)
    celery.conf.task_default_queue = flask_app.config['CELERY_TASK_DEFAULT_QUEUE']
    celery.Task = ContextTask
    return celery
