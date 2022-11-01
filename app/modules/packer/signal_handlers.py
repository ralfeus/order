def on_sale_order_model_preparing(sender, **_extra):
    from app.modules.packer.models import OrderPacker
    return OrderPacker.get_order_packer_for_sale_order(sender, details=_extra['details'])
