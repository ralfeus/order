''' 
Signal handlers for module Warehouse.
The module functionality is mainly invoked via signals from the core
or other modules. Those signal handlers are here
'''
from functools import reduce
import logging
from app.modules.warehouse.exceptions import WarehouseError
from app.purchase.models.purchase_order import PurchaseOrder

def on_admin_order_products_rendering(_sender, **_extra):
    from app.modules.warehouse.models.warehouse import Warehouse
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
    from app.modules.warehouse.models.order_product_warehouse import OrderProductWarehouse
    return OrderProductWarehouse.get_warehouse_for_order_product(sender)

def on_purchase_order_model_preparing(sender, **_extra):
    from app.modules.warehouse.models.purchase_order_warehouse import PurchaseOrderWarehouse
    return PurchaseOrderWarehouse.get_warehouse_for_purchase_order(sender)

def on_order_product_saving(order_product, payload, **_extra):
    from app import db
    from app.modules.warehouse.models.warehouse import Warehouse
    from app.modules.warehouse.models.order_product_warehouse import OrderProductWarehouse
    if payload.get('warehouse_id') is not None:
        warehouse = Warehouse.query.get(payload['warehouse_id'])
        if warehouse is None:
            raise WarehouseError(f"No warehouse <{payload['warehouse_id']}> is found")
    else:
        warehouse = None
    order_product_warehouse = OrderProductWarehouse.query.\
        filter_by(order_product_id=order_product.id).first()
    if warehouse is not None:
        if order_product_warehouse is None:
            order_product_warehouse = OrderProductWarehouse(order_product_id=order_product.id)
            db.session.add(order_product_warehouse)
        order_product_warehouse.warehouse = warehouse
    else:
        if order_product_warehouse is not None:
            db.session.delete(order_product_warehouse)

def on_purchase_order_deleting(sender: PurchaseOrder, **_extra):
    from app.modules.warehouse.models.purchase_order_warehouse import PurchaseOrderWarehouse
    PurchaseOrderWarehouse.query.filter_by(purchase_order_id=sender.id).delete()

def on_purchase_order_saving(purchase_order, warehouse_id=None, **kwargs):
    from app import db
    from app.modules.warehouse.models.warehouse import Warehouse
    from app.modules.warehouse.models.purchase_order_warehouse import PurchaseOrderWarehouse
    if warehouse_id is not None:
        warehouse = Warehouse.query.get(warehouse_id)
        if warehouse is None:
            raise WarehouseError(f"No warehouse <{warehouse_id}> is found")
    else:
        warehouse = None
    purchase_order_warehouse = PurchaseOrderWarehouse.query.\
        filter_by(purchase_order_id=purchase_order.id).first()
    if warehouse is not None:
        if purchase_order_warehouse is None:
            purchase_order_warehouse = PurchaseOrderWarehouse(purchase_order_id=purchase_order.id)
            db.session.add(purchase_order_warehouse)
        purchase_order_warehouse.warehouse = warehouse
    else:
        if purchase_order_warehouse is not None:
            db.session.delete(purchase_order_warehouse)

def on_sale_order_shipped(sender, **_extra):
    '''Handles shipped sale order (removes products from a local warehouse)'''
    logger = logging.getLogger('modules.warehouse.signal_handlers.on_sale_order_shipped()')
    logger.debug("Got signal from: %s", sender.id)
    from app.modules.warehouse.models.order_product_warehouse import OrderProductWarehouse
    for op in sender.order_products:
        op_warehouse = OrderProductWarehouse.query.get(op.id)
        if op_warehouse is not None:
            logger.debug("Product %s is to be taken from warehouse %s", op.product.id, op_warehouse.warehouse)
            op_warehouse.warehouse.sub_product(op.product, op.quantity)
        else:
            logger.debug("Product %s is NOT to be taken from any warehouse", op.product.id)

def on_purchase_order_delivered(sender, **_extra):
    '''Handles delivered purchase order (add products to a local warehouse)'''
    logger = logging.getLogger('modules.warehouse.signal_handlers.on_purchase_order_delivered()')
    logger.debug("Got signal from: %s", sender.id)
    from app.modules.warehouse.models.purchase_order_warehouse import PurchaseOrderWarehouse
    from app.orders.models import OrderStatus
    from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
    po_warehouse = PurchaseOrderWarehouse.query.get(sender.id)
    if po_warehouse is not None:
        logger.debug("Products of %s are to be put to the warehouse %s",
                     sender.id, po_warehouse.warehouse)
        for pp in sender.suborder.order_products:
            po_warehouse.warehouse.add_product(pp.product, pp.quantity)
        suborder_ids = [sos.id for sos in sender.suborder.order.suborders]
        pos_complete = reduce(
            lambda acc, po: acc and po.status == PurchaseOrderStatus.delivered,
            PurchaseOrder.query.filter(PurchaseOrder.suborder_id.in_(suborder_ids)),
            True)
        if pos_complete:
            logger.debug("All POs of order %s are delivered. Setting its status 'at_warehouse'",
                         sender.suborder.order)
            sender.suborder.order.status = OrderStatus.at_warehouse
    else:
        logger.debug("Products of %s will not be stored in any warehouse", sender.id)

def on_create_purchase_order_rendering(_sender, **_extra):
    from app.modules.warehouse.models.warehouse import Warehouse
    warehouses = Warehouse.query
    return {
        'fields': [
            {
                'label': 'Store in warehouse',
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
