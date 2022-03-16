'''Defines Sale Orders signals'''
from app import signals
sale_order_packed = signals.signal('sale_order.status.packed')
sale_order_shipped = signals.signal('sale_order.status.shipped')
admin_order_products_rendering = signals.signal('sale_order.admin_order_products.rendering')
order_product_model_preparing = signals.signal('sale_order.order_product_model.preparing')
order_product_saving = signals.signal('sale_order.order_product.saving')

__all__ = [sale_order_packed, sale_order_shipped, admin_order_products_rendering]
