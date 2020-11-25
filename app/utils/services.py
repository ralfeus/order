from celery import Celery

def get_celery(app_name):
    celery = Celery(
        app_name,
        broker='pyamqp://172.17.0.1',
        backend='rpc://',
        include=['app.jobs', 'app.purchase.jobs']
    )
    # celery.conf.add_defaults(flask_app.config)
    # celery.conf.task_default_queue = 'order'
    return celery

def init_celery(celery, flask_app):
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.config_from_object(flask_app.config)
    celery.Task = ContextTask
    return celery