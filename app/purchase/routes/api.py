from datetime import datetime
import logging
from operator import itemgetter

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, roles_required

from sqlalchemy import or_

from app import db
from app.purchase import bp_api_admin
from app.tools import prepare_datatables_query, modify_object

from app.models.address import Address
from app.orders.models import Order, Subcustomer
from app.purchase.models import Company, PurchaseOrder, PurchaseOrderStatus
from app.purchase.validators.purchase_order import PurchaseOrderValidator
from app.purchase.po_manager import create_purchase_orders
from exceptions import AtomyLoginError, PurchaseOrderError
from utils.atomy import atomy_login, atomy_login2

from app.purchase.models.vendor_manager import PurchaseOrderVendorManager

@bp_api_admin.route('/order', defaults={'po_id': None})
@bp_api_admin.route('/order/<po_id>')
@roles_required('admin')
def get_purchase_orders(po_id):
    ''' Returns all or selected purchase orders in JSON '''
    purchase_orders: list[PurchaseOrder] = PurchaseOrder.query
    if po_id is not None:
        purchase_orders = purchase_orders.filter_by(id=po_id)
        if purchase_orders.count() == 1:
            return jsonify(purchase_orders.first().to_dict())
    if request.args.get('status'):
        purchase_orders = purchase_orders.filter_by(
            status=PurchaseOrderStatus[request.args['status']].name)
    if request.args.get('draw') is not None: # Args were provided by DataTables
        purchase_orders, records_total, records_filtered = prepare_datatables_query(
            purchase_orders, request.values,
            or_(
                PurchaseOrder.id.like(f"%{request.values['search[value]']}%"),
                PurchaseOrder.customer.has(
                    Subcustomer.name.like(f"%{request.values['search[value]']}%")),
                PurchaseOrder.status.like(f'%{request.values["search[value]"]}%')
            )
        )
        return jsonify({
            'draw': request.values['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': [entry.to_dict() for entry in purchase_orders]
        })
    if purchase_orders.count() == 0:
        abort(Response("No purchase orders were found", status=404))
    else:
        return jsonify([entry.to_dict() for entry in purchase_orders])

@bp_api_admin.route('/order', methods=['POST'])
@roles_required('admin')
def admin_create_purchase_orders():
    '''
    Creates purchase order.
    Accepts order details in payload
    Returns JSON
    '''
    with PurchaseOrderValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't create a purchase order",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })

    payload = request.get_json()
    if not payload:
        abort(Response("No purchase order data was provided", status=400))
    order = Order.query.get(payload['order_id'])
    company = Company.query.get(payload['company_id'])
    address = Address.query.get(payload['address_id'])
    vendor = PurchaseOrderVendorManager.get_vendor(payload['vendor'], config=current_app.config)
    if not vendor:
        abort(Response("No vendor was found"))
    del payload['vendor']
    payload['purchase_restricted_products'] = payload.get('purchase_restricted_products', False)

    try:
        purchase_orders = create_purchase_orders(
            order, company, address, vendor, **payload
        )
    except PurchaseOrderError:
        return jsonify({
                'data': [],
                'error': f"Purchase orders for order {order.id} already exist",
                'status': 409
            })
    from app.purchase.jobs import post_purchase_orders
    try:
        task = post_purchase_orders.apply_async(retry=False, connect_timeout=1)
        current_app.logger.info("Post purchase orders task ID is %s", task.id)
    except Exception as ex:
        current_app.logger.warning("Created purchase orders but couldn't add background task")
        current_app.logger.warning(str(ex))

    return (jsonify({'data': [po.to_dict() for po in purchase_orders]}), 202)

@bp_api_admin.route('/order/<po_id>', methods=['POST'])
@roles_required('admin')
def update_purchase_order(po_id):
    logger = logging.getLogger('update_purchase_order')
    po: PurchaseOrder = PurchaseOrder.query.get(po_id)
    if po is None:
        abort(Response("No purchase order <{po_id}> was found", status=404))

    from app.purchase.jobs import post_purchase_orders, update_purchase_orders_status
    payload = request.get_json()
    try:
        if request.values.get('action') == 'repost':
            po.reset_status()
            db.session.commit()
            task = post_purchase_orders.apply_async(
                kwargs={'po_id': po.id}, retry=False, connect_timeout=1)
            # post_purchase_orders(po.id)
            logger.info("Reposting PO %s by %s", po_id, current_user)
            logger.info("Post purchase orders task ID is %s", task.id)
            result = jsonify({'data': [po.to_dict()]})
        elif request.values.get('action') == 'update_status':
            logger.info("Updating POs status")
            task = update_purchase_orders_status.apply_async(
                kwargs={'po_id': po_id}, retry=False, connect_timeout=1)
            logger.info("Update POs status task ID is %s", task.id)
            result = jsonify({'data': [po.to_dict()]})
        else:
            logger.info('Modifying purchase order %s by %s with data: %s',
                        po_id, current_user, payload)
            if not po.is_editable():
                return jsonify({
                    'data': po.to_dict(),
                    'error': f"The purchase order &lt;{po.id}&gt; isn't in editable state"
                })
            editable_attributes = ['customer_id', 'payment_account', 'purchase_date',
                'vendor', 'vendor_po_id']
            po = modify_object(po, payload, editable_attributes)
            if payload.get('status') is not None:
                po.set_status(payload['status'])
            result = jsonify({'data': [po.to_dict()]})
    except: # Exception as ex:
        logger.exception("Couldn't update PO %s", po_id)
        abort(Response(po_id, 500))
    db.session.commit()
    return result
    # task = post_purchase_orders() # For debug purposes only


@bp_api_admin.route('/company_list')
@roles_required('admin')
def get_companies():
    companies = Company.query.filter_by(enabled=True)
    return jsonify(sorted(
        [entry.to_dict() for entry in companies],
        key=itemgetter('name')))

@bp_api_admin.route('/status')
@roles_required('admin')
def get_statuses():
    return jsonify([i.name for i in PurchaseOrderStatus])

@bp_api_admin.route('/vendor')
@roles_required('admin')
def get_vendors():
    vendor_mgmt = PurchaseOrderVendorManager()
    return jsonify([v.to_dict() for v in vendor_mgmt.get_vendors(config=current_app.config)])

@bp_api_admin.route('/order/validate', methods=['POST'])
@roles_required('admin')
def validate_po_input():
    payload = request.get_json()
    if payload is None:
        abort(400)
    message = ''
    if payload.get('order_id'):
        order = Order.query.get(payload['order_id'])
        if order is not None:
            error_subcustomers = []
            for suborder in order.suborders:
                try:
                    atomy_login2(suborder.subcustomer.username,
                                suborder.subcustomer.password)
                except AtomyLoginError:
                    current_app.logger.info("Couldn't validate subcustomer %s", payload)
                    error_subcustomers.append(suborder.subcustomer.username)
            if len(error_subcustomers) > 0:
                message = "Couldn't validate subcustomers: " + ','.join(error_subcustomers)
    if message:
        return jsonify({'status': 'error', 'message': message})
    return jsonify({'status': 'success'})