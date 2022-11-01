"""Defines Sale Orders signals"""
from app import signals

# The signal is sent when JSON of SO is generated
sale_order_model_preparing = signals.signal("sale_order.sale_order_model.preparing")
# The signal is sent when SO create request is received after the SO is created
# The argument is SO object and creation payload in JSON
sale_order_created = signals.signal("sale_order.created")
# The signal is sent when SO status is set to <packed>
sale_order_packed = signals.signal("sale_order.status.packed")
# The signal is sent when SO status is set to <shipped>
sale_order_shipped = signals.signal("sale_order.status.shipped")
admin_order_products_rendering = signals.signal(
    "sale_order.admin_order_products.rendering"
)
user_create_sale_order_rendering = signals.signal(
    "sale_order.user_create_order.rendering"
)
# The signal is sent when JSON of the order product is generated
order_product_model_preparing = signals.signal(
    "sale_order.order_product_model.preparing"
)
order_product_saving = signals.signal("sale_order.order_product.saving")

__all__ = [
    admin_order_products_rendering,
    order_product_model_preparing,
    order_product_saving,
    sale_order_created,
    sale_order_packed,
    sale_order_shipped,
    sale_order_model_preparing,
    user_create_sale_order_rendering,
]
