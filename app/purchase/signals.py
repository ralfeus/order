'''Defines Purchase Orders signals'''
from app import signals
purchase_order_delivered = signals.signal('purchase_order.status.delivered')
create_purchase_order_rendering = signals.signal('purchase_order.create_order.rendering')
purchase_order_model_preparing = signals.signal('purchase_order.purchase_order_model.preparing')
purchase_order_saving = signals.signal('purchase_order.purchase_order.saving')
__all__ = [purchase_order_delivered, create_purchase_order_rendering, purchase_order_model_preparing,
           purchase_order_saving]
