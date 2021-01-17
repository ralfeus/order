from celery import Celery

def get_celery(app_name):
    celery = Celery(
        app_name,
        broker='pyamqp://127.0.0.1',
        backend='rpc://',
        include=['app.jobs', 'app.purchase.jobs']
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
