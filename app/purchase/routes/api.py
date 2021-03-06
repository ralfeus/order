from app.purchase.validators.purchase_order import PurchaseOrderValidator
from datetime import datetime
from operator import itemgetter

from flask import Response, abort, current_app, jsonify, request
from flask_security import roles_required

from sqlalchemy import or_
from werkzeug.exceptions import HTTPException

from app import db
from app.purchase import bp_api_admin
from app.tools import prepare_datatables_query, modify_object

from app.orders.models import Order, OrderStatus, Subcustomer
from app.purchase.models import Company, PurchaseOrder, PurchaseOrderStatus

from ..models.vendor_manager import PurchaseOrderVendorManager

@bp_api_admin.route('/order', defaults={'po_id': None})
@bp_api_admin.route('/order/<po_id>')
@roles_required('admin')
def get_purchase_orders(po_id):
    '''
    Returns all or selected purchase orders in JSON
    '''
    purchase_orders = PurchaseOrder.query
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
            'data': list(map(lambda entry: entry.to_dict(), purchase_orders))
        })
    if purchase_orders.count() == 0:
        abort(Response("No purchase orders were found", status=404))
    else:
        return jsonify(list(map(lambda entry: entry.to_dict(), purchase_orders)))

@bp_api_admin.route('/order', methods=['POST'])
@roles_required('admin')
def create_purchase_order():
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
    if not order:
        abort(Response("No order to purchase was found", status=400))

    company = Company.query.get(payload['company_id'])
    if not company:
        abort(Response("No counter agent company was found", status=400))

    vendor = PurchaseOrderVendorManager.get_vendor(payload['vendor'], config=current_app.config)
    if not vendor:
        abort(Response("No vendor was found"))

    purchase_orders = []
    for suborder in order.suborders:
        purchase_order = PurchaseOrder(
            suborder=suborder,
            customer=suborder.subcustomer,
            contact_phone=payload['contact_phone'],
            payment_phone=company.phone,
            status=PurchaseOrderStatus.pending,
            zip=company.address.zip,
            address_1=company.address.address_1,
            address_2=company.address.address_2,
            company=company,
            vendor=vendor.id,
            when_created=datetime.now()
        )
        purchase_orders.append(purchase_order)
        db.session.add(purchase_order)
        db.session.flush()
    order.set_status(OrderStatus.po_created, current_app)
    db.session.commit()
    
    from ..jobs import post_purchase_orders
    task = post_purchase_orders.apply_async(retry=False, connect_timeout=1)
    # post_purchase_orders()
    current_app.logger.info("Post purchase orders task ID is %s", task.id)

    return (jsonify({'data': list(map(lambda po: po.to_dict(), purchase_orders))}), 202)

@bp_api_admin.route('/order/<po_id>', methods=['POST'])
@roles_required('admin')
def update_purchase_order(po_id):
    po = PurchaseOrder.query.get(po_id)
    if po is None:
        abort(Response("No purchase order <{po_id}> was found", status=404))

    from ..jobs import post_purchase_orders, update_purchase_orders_status
    try:
        if request.values.get('action') == 'repost':
            po.reset_status()
            db.session.commit()
            task = post_purchase_orders.apply_async(
                kwargs={'po_id': po.id}, retry=False, connect_timeout=1)
            # post_purchase_orders(po.id)
            current_app.logger.info("Post purchase orders task ID is %s", task.id)
            result = jsonify({'data': [po.to_dict()]})
        elif request.values.get('action') == 'update_status':
            current_app.logger.info("Updating POs status")
            task = update_purchase_orders_status.apply_async(
                kwargs={'po_id': po_id}, retry=False, connect_timeout=1)
            current_app.logger.info("Update POs status task ID is %s", task.id)
            result = jsonify({'data': [po.to_dict()]})
        else:
            if not po.is_editable():
                return jsonify({
                    'data': po.to_dict(),
                    'error': f"The purchase order &lt;{po.id}&gt; isn't in editable state"
                })
            editable_attributes = ['payment_account', 'purchase_date',
                'status', 'vendor', 'vendor_po_id']
            po = modify_object(po, request.get_json(), editable_attributes)
            result = jsonify({'data': [po.to_dict()]})
    except: # Exception as ex:
        current_app.logger.exception("Couldn't update PO %s", po_id)
        abort(Response(po_id, 500))
    db.session.commit()
    return result
    # task = post_purchase_orders() # For debug purposes only


@bp_api_admin.route('/company')
@roles_required('admin')
def get_companies():
    companies = Company.query
    return jsonify(sorted(
        list(map(lambda entry: entry.to_dict(), companies)),
        key=itemgetter('name')))

@bp_api_admin.route('/status')
@roles_required('admin')
def get_statuses():
    return jsonify(list(map(lambda i: i.name, PurchaseOrderStatus)))

@bp_api_admin.route('/vendor')
@roles_required('admin')
def get_vendors():
    vendor_mgmt = PurchaseOrderVendorManager()
    return jsonify(list(map(lambda v: v.to_dict(), vendor_mgmt.get_vendors(config=current_app.config))))
