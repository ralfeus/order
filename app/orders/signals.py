'''Defines Sale Orders signals'''
from app import signals
sale_order_packed = signals.signal('sale_order.status.packed')
__all__ = [sale_order_packed]
