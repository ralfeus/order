''' 
Signal handlers for module Warehouse.
The module functionality is mainly invoked via signals from the core
or other modules. Those signal handlers are here
'''
import logging
from .exceptions import WarehouseError

def on_admin_order_products_rendering(_sender, **_extra):
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

def on_order_product_model_preparing(sender, **_extra):
    from .models.order_product_warehouse import OrderProductWarehouse
    return OrderProductWarehouse.get_warehouse_for_order_product(sender)

def on_order_product_saving(order_product, payload, **_extra):
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

def on_sale_order_packed(sender, **_extra):
    '''Handles packed sale order (removes products from a local warehouse)'''
    logger = logging.getLogger(f'modules.warehouse.signal_handlers.on_sale_order_packed()')
    logger.debug(f"Got signal from: {sender.id}")
    from .models.order_product_warehouse import OrderProductWarehouse
    for op in sender.order_products:
        op_warehouse = OrderProductWarehouse.query.get(op.id)
        if op_warehouse is not None:
            logger.debug(f"Product {op.product.id} is to be taken from warehouse {op_warehouse.warehouse}")
            op_warehouse.warehouse.sub_product(op.product, op.quantity)
        else:
            logger.debug(f"Product {op.product.id} is NOT to be taken from any warehouse")

def on_purchase_order_delivered(sender, **_extra):
    '''Handles delivered purchase order (add products to a local warehouse)'''
    from .models.warehouse import Warehouse
    local_warehouse = Warehouse.get_local()
    if local_warehouse is not None:
        for pp in sender.products:
            local_warehouse.add_product(pp.product, pp.quantity)
