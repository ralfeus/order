from app import create_app
from app.jobs import import_products

with create_app().app_context():
    import_products()