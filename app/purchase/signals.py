'''Defines Purchase Orders signals'''
from app import signals
purchase_order_delivered = signals.signal('purchase_order.status.delivered')
create_purchase_order_rendering = signals.signal('purchase_order.create_order.rendering')
__all__ = [purchase_order_delivered, create_purchase_order_rendering]
