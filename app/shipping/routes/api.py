from __future__ import annotations
from datetime import datetime
import logging
from operator import itemgetter
from typing import Any, Optional

from flask import Response, abort, current_app, jsonify, request
from flask_security import login_required, roles_required  # type: ignore

from app import db, cache
from app.tools import modify_object
from exceptions import NoShippingRateError
from app.models import Country
import app.orders.models as o
from app.shipping import bp_api_admin, bp_api_user
from app.shipping.models.shipping import Shipping

from exceptions import OrderError


@bp_api_admin.route("")
@roles_required("admin")
def admin_get_shipping_methods():
    return jsonify([shipping.to_dict() for shipping in Shipping.query])


@bp_api_user.route("", defaults={"country_id": None, "weight": None})
@bp_api_user.route("/<country_id>", defaults={"weight": None})
@bp_api_user.route("/<country_id>/<int:weight>")
@login_required
@cache.cached(timeout=86400, query_string=True)
def get_shipping_methods(country_id, weight):
    """Returns shipping methods available for specific country and weight (if both provided)"""
    country_name = ""
    country: Optional[Country] = None
    if country_id:
        country = Country.query.get(country_id)
        if country:
            country_name = country.name

    shipping_methods: list[Shipping] = Shipping.query.filter_by(enabled=True)
    result = []
    product_ids = []
    product_ids = (
        request.values.get("products").split(",") #type: ignore
        if request.values.get("products")
        else []
    )
    for shipping in shipping_methods:
        if shipping.can_ship(country=country, weight=weight, products=product_ids):
            result.append(shipping.to_dict())
            logging.debug("%s can ship to %s", shipping, country)
        else:
            logging.debug("%s can't ship to %s", shipping, country)

    if len(result) > 0:
        return jsonify(sorted(result, key=itemgetter("name")))
    abort(
        Response(
            f"Couldn't find shipping method to send {weight}g parcel to {country_name}",
            status=409,
        )
    )


@bp_api_user.route("/rate/<country>/<int:shipping_method_id>/<int:weight>")
@bp_api_user.route(
    "/rate/<country>/<int:weight>", defaults={"shipping_method_id": None}
)
@login_required
@cache.cached(timeout=86400)
def get_shipping_rate(country, shipping_method_id: int, weight: int):
    """
    Returns shipping cost for provided country and weight
    Accepts parameters:
        country - Destination country
        shipping_method_id - ID of the shipping method
        weight - package weight in grams
    Returns JSON
    """
    logger = logging.getLogger("get_shipping_rate()")
    logger.info("Calculating shipping rates to %s of weight %s", country, weight)
    shipping_methods = Shipping.query
    if shipping_method_id:
        shipping_methods = shipping_methods.filter_by(id=shipping_method_id)

    rates = {}
    for shipping_method in shipping_methods:
        if weight == 0:
            rates[shipping_method.id] = 0
        else:
            try:
                rates[shipping_method.id] = shipping_method.get_shipping_cost(
                    country, weight
                )
            except NoShippingRateError:
                pass
    if len(rates) > 0:
        if shipping_method_id:
            return jsonify({"shipping_cost": rates[shipping_method_id]})
        else:
            return jsonify(rates)
    else:
        abort(
            Response(
                f"Couldn't find rate for {weight}g parcel to {country.title()}",
                status=409,
            )
        )


# @bp_api_admin.route('/box')
# @roles_required('admin')
# def admin_get_shipping_boxes():
#     return jsonify([box.to_dict() for box in Box.query])


@bp_api_admin.route("/<shipping_method_id>", methods=["POST"])
@roles_required("admin")
def admin_save_shipping_method(shipping_method_id):
    """Creates or modifies existing shipping_method"""
    # with ShippingMethodValidator(request) as validator:
    #     if not validator.validate():
    #         return jsonify({
    #             'data': [],
    #             'error': "Couldn't update a shipping method",
    #             'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
    #                             for message in validator.errors]
    #         }), 400
    payload: dict[str, Any] = request.get_json() #type: ignore
    if shipping_method_id == "null":
        shipping_method = Shipping()
        db.session.add(shipping_method)
    else:
        shipping_method = Shipping.query.get(shipping_method_id)
        if not shipping_method:
            abort(
                Response(
                    f"No shipping_method <{shipping_method_id}> was found", status=400
                )
            )
    payload["discriminator"] = payload.get("type")

    modify_object(
        shipping_method, payload, ["name", "enabled", "notification", "discriminator"]
    )

    db.session.commit()
    return jsonify({"data": [shipping_method.to_dict()]})


@bp_api_admin.route("/<shipping_method_id>", methods=["DELETE"])
@roles_required("admin")
def delete_shipping_method(shipping_method_id):
    """Deletes existing shipping method"""
    shipping_method = Shipping.query.get(shipping_method_id)
    if not shipping_method:
        abort(
            Response(f"No shipping method <{shipping_method_id}> was found", status=404)
        )
    db.session.delete(shipping_method)
    db.session.commit()
    return jsonify({})


@bp_api_admin.route("/consign/<order_id>")
@roles_required("admin")
def consign_order(order_id: str):
    order: o.Order = o.Order.query.get(order_id)
    if order is None:
        abort(Response("Couldn't find an order {order_id}", 404))
    try:
        result = order.shipping.consign(
            order, config=current_app.config.get("SHIPPING_AUTOMATION") #type: ignore
        )
        order.tracking_id = result.consignment_id
        order.tracking_url = f'https://t.17track.net/en#nums={result.consignment_id}'
        db.session.commit()
        return jsonify({
            "status": "next_step_available" if result.next_step_url else "success", 
            "consignment_id": result.consignment_id,
            "next_step_message": result.next_step_message,
            "next_step_url": result.next_step_url
        })
    except NotImplementedError:
        return jsonify({
            "status": "error",
            "message": f"The order shipping method {order.shipping} doesn't support consignment",
        })
    except OrderError as e:
        return jsonify({"status": "error", "message": e.args})
