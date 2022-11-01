"""Root PV Stats module"""
from importlib import import_module
import os, os.path
from flask import Blueprint, Flask

from app.orders.signals import sale_order_model_preparing
from app.modules.packer.signal_handlers import on_sale_order_model_preparing

# from .signal_handlers import

bp_api_admin = Blueprint(
    "packer_api_admin", __name__, url_prefix="/api/v1/admin/order/packer"
)
bp_client_admin = Blueprint(
    "packer_client_admin",
    __name__,
    url_prefix="/admin/order/packers",
    template_folder="templates",
)
bp_api_user = Blueprint("packer_api_user", __name__, url_prefix="/api/v1/packer")
bp_client_user = Blueprint(
    "packer_client_user", __name__, url_prefix="/packer", template_folder="templates"
)

_current_dir = os.path.dirname(__file__)


def init(app: Flask):
    """Initializes a Packer module"""
    if app.config.get("modules") is None:
        app.config["modules"] = {}
    app.config["modules"]["packer"] = True
    _register_signals()
    _import_models()
    _register_routes(app)


def _register_signals():
    sale_order_model_preparing.connect(on_sale_order_model_preparing)


def _import_models():
    files = os.listdir(_current_dir + "/models")
    for file in files:
        if file.startswith("__"):
            continue
        import_module(__name__ + ".models." + os.path.splitext(file)[0])


def _register_routes(app: Flask):
    files = os.listdir(_current_dir + "/routes")
    for file in files:
        if file.startswith("__"):
            continue
        import_module(__name__ + ".routes." + os.path.splitext(file)[0])
    app.register_blueprint(bp_api_admin)
    app.register_blueprint(bp_client_admin)
