ORDER_STATUSES = {
    "Order Placed": PurchaseOrderStatus.posted,
    "Unpaid Deadline": PurchaseOrderStatus.payment_past_due,
    "Shipping": PurchaseOrderStatus.paid,
    "Processing order": PurchaseOrderStatus.paid,
    "Shipped": PurchaseOrderStatus.shipped,
    "Order Completed": PurchaseOrderStatus.delivered,
    "Cancel Order": PurchaseOrderStatus.cancelled,
}
def update_purchase_order_status(purchase_order: PurchaseOrder):
    logger = _logger.getChild("update_purchase_order_status")
    logger.info("Updating %s status", purchase_order.id)
    logger.debug("Logging in as %s", purchase_order.customer.username)
    session = [{"Cookie": atomy_login2(
        purchase_order.customer.username,
        purchase_order.customer.password
    )}]
    logger.debug("Getting POs from Atomy...")
    vendor_purchase_orders = __get_purchase_orders(session)
    _logger.debug("Got %s POs", len(vendor_purchase_orders))
    for o in vendor_purchase_orders:
        # logger.debug(str(o))
        if o["id"] == purchase_order.vendor_po_id:
            purchase_order.set_status(ORDER_STATUSES[o["status"]])
            return purchase_order

    raise NoPurchaseOrderError(
        "No corresponding purchase order for Atomy PO <%s> was found"
        % purchase_order.vendor_po_id
    )

def update_purchase_orders_status(self, subcustomer, 
                                    purchase_orders: list[PurchaseOrder]):
    logger = _logger.getChild("update_purchase_orders_status")
    logger.info("Updating %s POs status", len(purchase_orders))
    logger.debug("Attempting to log in as %s...", subcustomer.name)
    session = [{"Cookie": atomy_login2(
        purchase_orders[0].customer.username,
        purchase_orders[0].customer.password
    )}]
    logger.debug("Getting subcustomer's POs")
    vendor_purchase_orders = __get_purchase_orders(session)
    logger.debug("Got %s POs", len(vendor_purchase_orders))
    for o in vendor_purchase_orders:
        # logger.debug(str(o))
        if ORDER_STATUSES[o["status"]] == PurchaseOrderStatus.posted:
            logger.debug("Skipping PO %s", o["id"])
            continue
        filtered_po = [
            po for po in purchase_orders if po and po.vendor_po_id == o["id"]
        ]
        try:
            filtered_po[0].set_status(ORDER_STATUSES[o["status"]])
        except IndexError:
            logger.warning(
                "No corresponding purchase order for Atomy PO <%s> was found",
                o["id"],
            )

def __get_purchase_orders(self, session_headers: list[dict[str, str]]):
    logger = _logger.getChild("__get_purchase_orders")
    logger.debug("Getting purchase orders")
    res = get_html(
        url=f"{URL_BASE}/mypage/orderList?"
        + "psearchMonth=12&startDate=&endDate=&orderStatus=all&pageIdx=2&rowsPerPage=100",
        headers=session_headers + [{"Cookie": "KR_language=en"}],
    )

    orders = [
        {
            "id": element.cssselect("input[name='hSaleNum']")[0].attrib["value"],
            "status": element.cssselect("span.m-stat")[0].text.strip(),
        }
        for element in res.cssselect("div.my_odr_gds li")
    ]
    return orders
