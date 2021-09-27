'''Defines Purchase Orders signals'''
from app import signals
purchase_order_delivered = signals.signal('purchase_order.status.delivered')
__all__ = [purchase_order_delivered]
