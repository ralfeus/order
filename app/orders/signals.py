"""Defines Sale Orders signals"""
from app import signals

# The signal is sent when JSON of SO is generated
sale_order_model_preparing = signals.signal("sale_order.sale_order_model.preparing")
# The signal is sent when SO create request is received after the SO is created
# The argument is SO object and creation payload in JSON
sale_order_created = signals.signal("sale_order.created")
# The signal is sent when SO status changes
# The argument is SO object, keyword arguments are old_status and new_status
# (OrderStatus; old_status is None for a new order).
# Use on_status_change() to subscribe to particular transitions only.
sale_order_status_changed = signals.signal("sale_order.status.changed")
# The signal is sent when SO shipping method is changed
# The argument is SO object (already carrying the new shipping) and old_shipping
sale_order_shipping_changed = signals.signal("sale_order.shipping.changed")
# The signal is sent when the boxes configuration of an SO is updated.
# The argument is the SO object (already carrying the new boxes list).
sale_order_boxes_changed = signals.signal("sale_order.boxes.changed")
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


# (handler, from_status, to_status) → receiver connected by on_status_change()
_status_receivers = {}


def on_status_change(handler, from_status=None, to_status=None):
    """Subscribe *handler* to sale_order_status_changed for matching transitions.

    *handler* is called as ``handler(order, old_status=..., new_status=...)``
    only when the transition matches: ``from_status`` and ``to_status`` are
    OrderStatus values, None matches any status.

    Returns the connected receiver, which is held strongly (it is a closure
    and would otherwise be garbage-collected); pass it to
    ``sale_order_status_changed.disconnect()`` to unsubscribe.  Subscribing
    the same handler for the same transition again (e.g. from a second app
    instance) reuses that receiver, so the handler still runs once.
    """
    key = (handler, from_status, to_status)
    if key in _status_receivers:
        receiver = _status_receivers[key]
        # Reconnect in case it was disconnected; blinker ignores duplicates
        sale_order_status_changed.connect(receiver, weak=False)
        return receiver

    def receiver(order, old_status=None, new_status=None, **extra):
        if from_status is not None and old_status != from_status:
            return
        if to_status is not None and new_status != to_status:
            return
        handler(order, old_status=old_status, new_status=new_status, **extra)

    _status_receivers[key] = receiver
    sale_order_status_changed.connect(receiver, weak=False)
    return receiver


__all__ = [
    "admin_order_products_rendering",
    "on_status_change",
    "order_product_model_preparing",
    "order_product_saving",
    "sale_order_boxes_changed",
    "sale_order_created",
    "sale_order_status_changed",
    "sale_order_shipping_changed",
    "sale_order_model_preparing",
    "user_create_sale_order_rendering",
]
