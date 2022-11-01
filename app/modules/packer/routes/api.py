"""API routes for warehouse module"""
from datetime import datetime

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, roles_required
from sqlalchemy import not_

from app import db
from app.modules.packer.models.order_packer import OrderPacker
from app.modules.packer.models.packer import Packer
from app.orders.models.order import Order
from app.tools import modify_object, prepare_datatables_query

from app.modules.packer import bp_api_admin


@bp_api_admin.route("")
@roles_required("admin")
def admin_get_order_packers():
    """Returns all or selected warehouses in JSON"""
    orders = Order.query.filter(not_(Order.id.like(r"%draft%")))
    if request.values.get("draw") is not None:  # Args were provided by DataTables
        return _filter_objects(orders, request.values)

    return jsonify(
        {"data": [entry.to_dict(partial=["id", "packer"]) for entry in orders]}
    )


@bp_api_admin.route("/packer")
@roles_required("admin")
def admin_get_packers():
    """Returns packer names"""
    packers = Packer.query
    return {"data": [entry.to_dict() for entry in packers]}, 200


@bp_api_admin.route("/<order_id>", methods=["POST"])
@roles_required("admin")
def admin_save_order_packer(order_id):
    """Modify the order packer"""
    logger = current_app.logger.getChild("admin_save_order_packer")
    order_packer = OrderPacker.query.get(order_id)
    if order_packer is None:
        order = Order.query.get(order_id)
        if order is None:
            abort(Response(f"No order {order_id} was found", status=404))
    payload = request.get_json()
    logger.info(
        "Modifying order packer %s by %s with data: %s",
        order_id, current_user, payload,
    )
    if (payload['packer'] == ''):
        db.session.delete(order_packer)
        order_packer.packer = None
    else:
        if Packer.query.get(payload["packer"]) is None:
            logger.info("No packer %s is there yet. Adding new", payload["packer"])
            db.session.add(Packer(name=payload["packer"], when_created=datetime.now()))
            db.session.flush()
        if order_packer is None:
            order_packer = OrderPacker(order_id=order_id)
            db.session.add(order_packer)
        modify_object(order_packer, payload, ["packer"])
    db.session.commit()
    return jsonify({"data": [order_packer.to_dict()]})


def _filter_objects(entities, filter_params):
    entities, records_total, records_filtered = prepare_datatables_query(
        entities, filter_params, None
    )
    return jsonify(
        {
            "draw": int(filter_params["draw"]),
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": [
                entry.to_dict(partial=["id", "packer", "when_created", "when_changed"])
                for entry in entities
            ],
        }
    )
