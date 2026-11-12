from flask import Blueprint

from .models.eurocargo_shipping import EurocargoShipping  # noqa: F401 - needed for SQLAlchemy

bp_api_admin = Blueprint('shipping_eurocargo_api_admin', __name__,
                         url_prefix='/api/v1/admin/shipping/eurocargo')
bp_client_admin = Blueprint('shipping_eurocargo_client_admin', __name__,
                             url_prefix='/admin/shipping/eurocargo',
                             static_folder='static',
                             template_folder='templates')


def register_blueprints(flask_app):
    from . import routes  # noqa: F401
    from app.orders.signals import sale_order_shipped
    from .signal_handlers import on_sale_order_shipped
    sale_order_shipped.connect(on_sale_order_shipped)
    from .cli import eurocargo_cli
    flask_app.cli.add_command(eurocargo_cli)
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_client_admin)
