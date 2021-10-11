'''Defines Sale Orders signals'''
from app import signals
sale_order_packed = signals.signal('sale_order.status.packed')
admin_order_products_rendering = signals.signal('sale_order.admin_order_products.rendering')
order_product_model_preparing = signals.signal('sale_order.order_product_model.preparing')

__all__ = [sale_order_packed, admin_order_products_rendering]
