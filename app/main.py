import sys
sys.path.append('..')

from app import create_app, celery
app = create_app()