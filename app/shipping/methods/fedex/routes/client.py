'''Client routes for EMS shipping'''
import json
from flask import Response, abort, current_app, render_template, request
from flask_security import roles_required

from app import db
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from ..models.fedex import Fedex

from .. import bp_client_admin

@bp_client_admin.route('/')
@roles_required('admin')
def admin_edit():
    pass
