from celery import Celery

def get_celery(flask_app):
    celery = Celery(
        flask_app.import_name,
        broker='pyamqp://',
        backend='rpc://',
        include=['app.jobs']
    )
    # celery.conf.add_defaults(flask_app.config)
    celery.config_from_object(flask_app.config)
    # celery.conf.task_default_queue = 'order'

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
