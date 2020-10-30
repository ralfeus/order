import sys
sys.path.append('..')

from app import create_app, celery
create_app()
app = celery