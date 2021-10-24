'''Root Warehouse module'''
from importlib import import_module
import os, os.path
from flask import Blueprint, Flask

from .exceptions import WarehouseError

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
    sale_order_packed.connect(_on_sale_order_packed)
    admin_order_products_rendering.connect(_on_admin_order_products_rendering)
    order_product_model_preparing.connect(_on_order_product_model_preparing)
    from app.purchase.signals import purchase_order_delivered
    purchase_order_delivered.connect(_on_purchase_order_delivered)
    order_product_saving.connect(_on_order_product_saving)

def _on_admin_order_products_rendering(_sender, **_extra):
    from .models.warehouse import Warehouse
    warehouses = Warehouse.query
    return {
        'fields': [
            {
                'label': 'Take from warehouse',
                'name': 'warehouse_id',
                'type': 'select2',
                'options': [{
                    'value': warehouse.id,
                    'label': warehouse.name
                } for warehouse in warehouses],
                'opts': {
                    'allowClear': 1,
                    'placeholder': {
                        'id': '',
                        'text': '-- None --'
                    }
                }
            }
        ],
        'columns': [
            {'name': 'Warehouse', 'data': 'warehouse'}
        ]
    }

def _on_order_product_model_preparing(sender, **_extra):
    from .models.order_product_warehouse import OrderProductWarehouse
    return OrderProductWarehouse.get_warehouse_for_order_product(sender)

def _on_order_product_saving(order_product, payload, **_extra):
    from app import db
    from .models.warehouse import Warehouse
    from .models.order_product_warehouse import OrderProductWarehouse
    if payload.get('warehouse_id') is not None:
        warehouse = Warehouse.query.get(payload['warehouse_id'])
        if warehouse is None:
            raise WarehouseError(f"No warehouse <{payload['warehouse_id']}> is found")
    else:
        warehouse = None
    order_product_warehouse = OrderProductWarehouse.query.filter_by(order_product_id=order_product.id).first()
    if warehouse is not None:
        if order_product_warehouse is None:
            order_product_warehouse = OrderProductWarehouse(order_product_id=order_product.id)
            db.session.add(order_product_warehouse)
        order_product_warehouse.warehouse = warehouse
    else:
        if order_product_warehouse is not None:
            db.session.delete(order_product_warehouse)

def _on_sale_order_packed(sender, **_extra):
    '''Handles packed sale order (removes products from a local warehouse)'''
    from .models.warehouse import Warehouse
    local_warehouse = Warehouse.get_local()
    if local_warehouse is not None:
        for op in sender.order_products:
            local_warehouse.sub_product(op.product, op.quantity)

def _on_purchase_order_delivered(sender, **_extra):
    '''Handles delivered purchase order (add products to a local warehouse)'''
    from .models.warehouse import Warehouse
    local_warehouse = Warehouse.get_local()
    if local_warehouse is not None:
        for pp in sender.products:
            local_warehouse.add_product(pp.product, pp.quantity)
