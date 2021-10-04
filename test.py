from app import create_app
from app.jobs import import_products

app = create_app()
app.app_context().push()
import_products()