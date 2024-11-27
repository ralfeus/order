'''API routes for FedEx module'''
from datetime import datetime
from typing import Any

from flask import request
from flask_security import roles_required
from sqlalchemy import or_

from app import cache, db
from app.shipping.methods.fedex.models.fedex import Fedex
from app.shipping.models.shipping import Shipping
from app.tools import modify_object

from ..models.fedex_setting import FedexSetting
from .. import bp_api_admin

@bp_api_admin.route("/<shipment_id>")
@roles_required('admin')
def admin_get_settings(shipment_id: int):
    '''Returns settings of FedEx shipment'''
    fedex: Fedex = Shipping.query.get(shipment_id)
    if fedex is None:
        return {'error': f"No shipment <{shipment_id}> was found"}, 404
    return {'data': fedex.to_dict()}, 200

@bp_api_admin.route("/<shipment_id>", methods=['POST'])
@roles_required('admin')
def admin_save_settings(shipment_id: int):
    '''Saves settings of FedEx shipment'''
    fedex = Shipping.query.get(shipment_id)
    if fedex is None:
        return {'status': 'error', 'message': f"No shipment <{shipment_id}> was found"}, 404
    payload: dict[str, Any] = request.get_json() # type: ignore
    modify_object(fedex.settings, payload, ['service_type'])
    db.session.commit()
    cache.clear()
    return {'status': 'success', 'data': fedex.to_dict()}, 200

