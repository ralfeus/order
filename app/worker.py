from celery.signals import worker_process_init

from app import celery, db

# Keep a reference to the Flask app so the post-fork signal handler
# can push an app context without relying on the implicit current_app.
flask_app = None

def create():
    global flask_app
    from app import create_app
    flask_app = create_app()

create()

@worker_process_init.connect
def dispose_db_pool(*args, **kwargs):
    ''' After Celery forks a child worker process the parent's connection-pool
        file descriptors are inherited by the child.  Multiple workers sharing
        the same underlying MySQL socket interleave protocol frames, which
        causes "Commands out of sync" (MySQLdb 2014).
        Disposing the pool immediately after the fork forces each child to open
        its own fresh connections. '''
    with flask_app.app_context():
        db.engine.dispose()
