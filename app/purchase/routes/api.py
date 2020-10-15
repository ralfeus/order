from datetime import datetime

from flask import Response, abort, current_app, jsonify, request
from flask_security import roles_required

from app import db
from app.purchase import bp_api_admin
from app.tools import prepare_datatables_query

from app.orders.models import Order, OrderStatus
from app.purchase.models import Company, PurchaseOrder, PurchaseOrderStatus

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
            PurchaseOrder.id.like(f"%{request.values['search[value]']}%")
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
def create_purhase_order():
    '''
    Creates purchase order.
    Accepts order details in payload
    Returns JSON
    '''
    payload = request.get_json()
    if not payload:
        abort(Response("No purchase order data was provided", status=400))
    
    order = Order.query.get(payload['order_id'])
    if not order:
        abort(Response("No order to purchase was found", status=400))

    company = Company.query.get(payload['company_id'])
    if not company:
        abort(Response("No counter agent company was found", status=400))

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
            when_created=datetime.now()
        )
        purchase_orders.append(purchase_order)
        db.session.add(purchase_order)
    order.status = OrderStatus.po_created
    db.session.commit()
    
    from app.jobs import post_purchase_orders
    task = post_purchase_orders.delay()
    current_app.logger.info("Post purchase orders task ID is %s", task.id)

    return (jsonify(list(map(lambda po: po.to_dict(), purchase_orders))), 202)

@bp_api_admin.route('/order/repost', methods=['POST'])
@roles_required('admin')
def repost_failed_purchase_orders():
    failed_po = PurchaseOrder.query.filter_by(status=PurchaseOrderStatus.failed)
    for po in failed_po:
        po.status = PurchaseOrderStatus.pending
    db.session.commit()
    from app.jobs import post_purchase_orders
    # task = post_purchase_orders.delay()
    task = post_purchase_orders()
    # from app.tools import start_job
    # pid = start_job('test', current_app.logger)
    current_app.logger.info("Post purchase orders task ID is %s", task.id)

    return (jsonify(list(map(lambda po: po.to_dict(), failed_po))), 202)

@bp_api_admin.route('/company')
@roles_required('admin')
def get_companies():
    companies = Company.query
    return jsonify(list(map(lambda entry: entry.to_dict(), companies)))
