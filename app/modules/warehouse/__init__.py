'''Root Warehouse module'''
from importlib import import_module
import os, os.path
from flask import Blueprint, Flask

from .signal_handlers import on_admin_order_products_rendering, \
    on_order_product_model_preparing, on_order_product_saving, on_sale_order_packed, \
    on_purchase_order_delivered

bp_api_admin = Blueprint('warehouse_api_admin', __name__,
                         url_prefix='/api/v1/admin/warehouse')
bp_client_admin = Blueprint('warehouse_client_admin', __name__,
                            url_prefix='/admin/warehouses', template_folder='templates')

_current_dir = os.path.dirname(__file__)

def init(app: Flask):
    '''Initializes a Warehouse module'''
    if app.config.get('modules') is None:
        app.config['modules'] = {}
    app.config['modules']['warehouse'] = True
    _register_signals()
    _import_models()
    _register_routes(app)

def _import_models():
    files = os.listdir(_current_dir + '/models')
    for file in files:
        if file.startswith('__'):
            continue
        import_module(__name__ + '.models.' + os.path.splitext(file)[0])

def _register_routes(app):
    files = os.listdir(_current_dir + '/routes')
    for file in files:
        if file.startswith('__'):
            continue
        import_module(__name__ + '.routes.' + os.path.splitext(file)[0])
    app.register_blueprint(bp_api_admin)
    app.register_blueprint(bp_client_admin)


def _register_signals():
    from app.orders.signals import sale_order_packed, \
        admin_order_products_rendering, order_product_model_preparing, \
        order_product_saving
    sale_order_packed.connect(on_sale_order_packed)
    admin_order_products_rendering.connect(on_admin_order_products_rendering)
    order_product_model_preparing.connect(on_order_product_model_preparing)
    from app.purchase.signals import purchase_order_delivered
    purchase_order_delivered.connect(on_purchase_order_delivered)
    order_product_saving.connect(on_order_product_saving)
