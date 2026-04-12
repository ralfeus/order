from flask import Blueprint

from .models.separate_shipping import SeparateShipping  # noqa: F401 - needed for SQLAlchemy

bp_api_admin = Blueprint('shipping_separate_api_admin', __name__,
                         url_prefix='/api/v1/admin/shipping/separate')
bp_client_admin = Blueprint('shipping_separate_client_admin', __name__,
                             url_prefix='/admin/shipping/separate',
                             static_folder='static',
                             template_folder='templates')


def register_blueprints(flask_app):
    from . import routes  # noqa: F401
    from app.orders.signals import sale_order_shipped
    from .signal_handlers import on_sale_order_shipped
    sale_order_shipped.connect(on_sale_order_shipped)
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_client_admin)
