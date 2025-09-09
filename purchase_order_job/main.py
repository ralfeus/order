import os
import json

import requests
from post_po import post_purchase_order
import po_types
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    po_json = os.environ.get("PO_JSON")
    if not po_json:
        logger.error("PO_JSON environment variable not set.")
        return

    try:
        po_dict = json.loads(po_json)
        purchase_order = po_types.PurchaseOrder(**po_dict)
        logger.info(f"Purchase order id: {purchase_order.id}")
        updated_po, unavailable_products = post_purchase_order(purchase_order)
        logger.info(f"Updated purchase order: {updated_po}")
        logger.info(f"Unavailable products: {unavailable_products}")
        if os.environ.get("CALLBACK_URL"):
            requests.post(url=os.environ.get("CALLBACK_URL", ""), json={
                "job_id": os.environ.get("JOB_ID"),
                "vendor_po_id": updated_po.vendor_po_id,
                "payment_account": updated_po.payment_account,
                "total_krw": updated_po.total_krw,
                "unavailable_products": unavailable_products
            })

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode PO_JSON: {e}")
    except Exception as e:
        logger.exception(f"Failed to create PurchaseOrder: {e}")

if __name__ == "__main__":
    main()
