'''API endpoints for sale order management'''
from datetime import datetime
import logging
from more_itertools import map_reduce
import re

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from sqlalchemy import and_, not_, or_
from sqlalchemy.exc import IntegrityError, OperationalError, DataError

from exceptions import EmptySuborderError, NoShippingRateError, \
    OrderError, SubcustomerParseError, ProductNotFoundError, UnfinishedOrderError

from app import db
from app.models import Country
from app.orders import bp_api_admin, bp_api_user
from app.orders.models.order import OrderBox
from app.orders.models import Order, OrderProduct, OrderProductStatus, \
    OrderStatus, Suborder, Subcustomer
from app.orders.validators.order import OrderEditValidator, OrderValidator
from app.products.models import Product
from app.shipping.models import Shipping, PostponeShipping
from app.tools import cleanse_payload, prepare_datatables_query, modify_object, stream_and_close

from ..utils import parse_subcustomer

@bp_api_admin.route('/<order_id>', methods=['DELETE'])
@roles_required('admin')
def delete_order(order_id):
    '''
    Deletes specified order
    '''
    order = Order.query.get(order_id)
    if order is None:
        abort(Response(f"No order <{order_id}> was found", status=404))
    if order.status in [OrderStatus.po_created, OrderStatus.shipped]:
        abort(Response(f"Can't delete order in status <{order.status.name}>", status=409))
    if order.invoice is not None:
        abort(Response(f"""
            There is an invoice {order.invoice} assigned to the order <{order_id}>. 
            Can't delete order with invoice created""", status=409))

    for suborder in order.suborders:
        for op in suborder.order_products:
            db.session.delete(op)
        db.session.delete(suborder)
    db.session.delete(order)
    db.session.commit()
    current_app.logger.warning(
        "Sale Order <%s> of customer <%s> created on <%s> is deleted by <%s>",
        order_id, order.customer_name, order.when_created, current_user.username)
    return Response(status=200)
        

@bp_api_admin.route('', defaults={'order_id': None})
@bp_api_admin.route('/<order_id>')
@roles_required('admin')
def admin_get_orders(order_id):
    ''' Returns all or selected orders in JSON '''
    orders = Order.query.filter(Order.status != OrderStatus.draft)
    if order_id is not None:
        orders = orders.filter_by(id=order_id)
        if orders.count() == 1:
            return jsonify(orders.first().to_dict(details=True))
    else:
        orders = orders.filter(not_(Order.id.like('%draft%')))
    if request.values.get('status'):
        orders = orders.filter(
            Order.status.in_(request.values.getlist('status')))
    if request.values.get('user_id'):
        orders = orders.filter_by(user_id=request.values['user_id'])
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return filter_orders(orders, request.values)

    # if orders.count() == 0:
    #     abort(Response("No orders were found", status=404))
    else:
        return jsonify(
            [entry.to_dict(details=request.values.get('details')) for entry in orders])

@bp_api_user.route('', defaults={'order_id': None})
@bp_api_user.route('/<order_id>')
@login_required
def user_get_orders(order_id):
    orders = Order.query
    if not current_user.has_role('admin'):
        orders = orders.filter_by(user=current_user)
    if order_id is not None:
        orders = orders.filter_by(id=order_id)
        if orders.count() == 1:
            return jsonify(orders.first().to_dict(details=True))

    if request.values.get('status'):
        orders = orders.filter_by(status=OrderStatus[request.args['status']].name)
    if request.values.get('to_attach') is not None:
        orders = orders.join(PostponeShipping).filter(
            Order.status != OrderStatus.shipped)
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return filter_orders(orders.filter(Order.status != OrderStatus.draft), request.values)
    if orders.count() == 0:
        abort(Response("No orders were found", status=404))
    else:
        return jsonify([entry.to_dict(details=request.values.get('details')) 
                        for entry in orders])

def filter_orders(orders, filter_params):
    orders = orders.order_by(Order.purchase_date_sort)
    orders, records_total, records_filtered = prepare_datatables_query(
        orders, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry .to_dict() for entry in orders]
    })

def _set_draft(order):
    draft_order_id_prefix = f'ORD-draft-{current_user.id}-'
    if not order.id.startswith(draft_order_id_prefix):
        last_draft = Order.query \
            .filter(Order.id.startswith(draft_order_id_prefix)) \
            .order_by(Order.seq_num.desc()).first()
        order.seq_num = last_draft.seq_num + 1 if last_draft else 1
        order.id = draft_order_id_prefix + str(order.seq_num)
    order.status = OrderStatus.draft
    return order

@bp_api_user.route('', methods=['POST'])
@login_required
def user_create_order():
    '''
    Creates order.
    Accepts order details in payload
    Returns JSON
    '''
    logger = current_app.logger.getChild('user_create_order')
    with OrderValidator(request) as validator:
        if not validator.validate():
            return Response(f"Couldn't create an Order\n{validator.errors}", status=409)

    payload = request.get_json()
    logger.debug(f"Create sale order with data: {payload}")
    result = {}
    shipping = Shipping.query.get(payload['shipping'])
    country = Country.query.get(payload['country'])
    with db.session.no_autoflush:
        order = Order(
            user=current_user,
            customer_name=payload['customer_name'],
            address=payload['address'],
            country_id=payload['country'],
            country=country,
            zip=payload['zip'],
            shipping=shipping,
            phone=payload['phone'],
            comment=payload['comment'],
            subtotal_krw=0,
            status=OrderStatus.pending,
            when_created=datetime.now()
        )
        if 'draft' in payload.keys() and payload['draft']:
            order = _set_draft(order)
        logger.info("Order %s is created", order.id)

        order.attach_orders(payload.get('attached_orders'))
        db.session.add(order)
        # order_products = []
        errors = []
        # ordertotal_weight = 0
        if payload.get('params') is not None and \
           payload['params'].get('shipping') is not None:
            _set_shipping_params(order, payload['params']['shipping'])
        add_suborders(order, payload['suborders'], errors)
        try:
            order.update_total()
        except NoShippingRateError:
            abort(Response("No shipping rate available", status=409))

    try:
        db.session.commit()
        logger.debug("Order %s is saved", order.id)
        result = {
            'status': 'warning' if len(errors) > 0 else 'success',
            'order_id': order.id,
            'message': errors
        }
    except DataError as ex:
        db.session.rollback()
        message = ex.orig.args[1]
        table = re.search('INSERT INTO (.+?) ', ex.statement).groups()[0]
        if table:
            if table == 'subcustomers':
                message = "Subcustomer error: " + message + " " + str(ex.params[2:5])
        result = {
            'status': 'error',
            'message': f"""Couldn't add order due to input error. Check your form and try again.
                           {message}"""
        }
    except (IntegrityError, OperationalError) as ex:
        db.session.rollback()
        result = {
            'status': 'error',
            'message': f"""Couldn't add order due to input error. Check your form and try again.
                           {str(ex.args)}"""
        }
    return jsonify(result)

def _set_shipping_params(order, shipping_params):
    for k, v in shipping_params.items():
        order.params['shipping.' + k] = v

def add_suborders(order, suborders, errors):
    suborders_count = 0
    for suborder_data in suborders:
        suborder_data_subset = suborder_data.copy()
        for index in range(0, len(suborder_data['items']), 10):
            suborder_data_subset['items'] = suborder_data['items'][index:index + 10]
            try:
                _add_suborder(order, suborder_data_subset, errors)
                db.session.flush()
                suborders_count += 1
            except EmptySuborderError as ex:
                errors.append(f"Suborder for <{ex.args[0]}> is empty. Skipped")
    if suborders_count == 0:
        abort(Response("The order is empty. Please add at least one product.", status=409))

def _add_suborder(order, suborder_data, errors):
    try:
        subcustomer, is_new = parse_subcustomer(suborder_data['subcustomer'])
        if is_new:
            db.session.add(subcustomer)
        if len(suborder_data['items']) == 1 and suborder_data['items'][0]['item_code'] == '':
            raise EmptySuborderError(subcustomer.username)
        suborder = Suborder(
            order=order,
            subcustomer=subcustomer,
            buyout_date=datetime.strptime(suborder_data['buyout_date'], '%Y-%m-%d') \
                if suborder_data.get('buyout_date') else None,
            local_shipping=0,
            when_created=datetime.now()
        )
        if suborder.buyout_date:
            if not order.purchase_date or order.purchase_date > suborder.buyout_date:
                order.set_purchase_date(suborder.buyout_date)

        current_app.logger.debug('Created instance of Suborder %s', suborder)
        # db.session.add(suborder)
        order.suborders.append(suborder)
        db.session.flush()
    except SubcustomerParseError:
        abort(Response(f"""Couldn't find subcustomer and provided data
                        doesn't allow to create new one. Please provide
                        new subcustomer data in format: 
                        <ID>, <Name>, <Password>
                        Erroneous data is: {suborder_data['subcustomer']}""",
                    status=400))

    suborder_products = map_reduce(suborder_data['items'],
        keyfunc=lambda op: op['item_code'],
        valuefunc=lambda op: int(op['quantity']),
        reducefunc=sum
    )
    suborder_products = [{'item_code': i[0], 'quantity': i[1]}
                            for i in suborder_products.items()]
    for item in suborder_products:
        try:
            add_order_product(suborder, item, errors)
        except:
            # current_app.logger.exception("Couldn't add product %s", item['item_code'])
            pass

@bp_api_user.route('/<order_id>', methods=['POST'])
@login_required
def user_save_order(order_id):
    ''' Updates existing order '''
    logger = logging.getLogger(f'user_save_order:{order_id}')
    order = Order.query.get(order_id) if 'admin' in current_user.roles \
        else Order.query.filter_by(id=order_id, user=current_user).first()
    if not order:
        abort(Response(f"No order <{order_id}> was found", status=404))
    if not order.is_editable() and not current_user.has_role('admin'):
        abort(Response(f"The order <{order_id}> isn't in editable state", status=405))
    with OrderEditValidator(request) as validator:
        if not validator.validate():
            return Response(f"Couldn't update an Order\n{validator.errors}", status=409)

    payload = request.get_json()
    logger.info('Modifying order by %s with data: %s',
                current_user, payload)
    if not ('draft' in payload.keys() and payload['draft']) and order.status == OrderStatus.draft:
        db.session.delete(order)
        return user_create_order()

    errors = []
    with db.session.no_autoflush:
        _update_order(order, payload)

        # Edit or add order products
        if payload.get('suborders'):
            order_products = list(order.order_products)
            for suborder_data in payload['suborders']:
                _update_suborder(order, order_products, suborder_data, errors)
            db.session.flush()
        
            # Remove order products
            for order_product in order_products:
                current_app.logger.info("Removing product %s from suborder %s",
                    order_product.product_id, order_product.suborder_id)
                order_product.status_history.delete(synchronize_session='fetch')
                order_product.suborder.order_products. \
                    filter_by(id=order_product.id).delete(synchronize_session='fetch')
            # Remove empty suborders
            for suborder in order.suborders:
                if suborder.order_products.count() == 0:
                    current_app.logger.info("Removing suborder %s as it has no products.",
                        suborder.id)
                    db.session.delete(suborder)
        db.session.flush()
        try:
            order.update_total()
        except NoShippingRateError:
            abort(Response("No shipping rate available", status=409))


    result = None
    try:
        db.session.commit()
        result = {
            'status': 'warning' if len(errors) > 0 else 'updated',
            'order_id': order.id,
            'message': errors
        }
    except (IntegrityError, OperationalError):
        result = {
            'status': 'error',
            'message': "Couldn't modify order due to input error. Check your form and try again."
        }
    return jsonify(result)

def _update_order(order, payload):
    if payload.get('customer_name') and order.customer_name != payload['customer_name']:
        order.customer_name = payload['customer_name']
    if payload.get('address') and order.address != payload['address']:
        order.address = payload['address']
    if payload.get('country') and order.country_id != payload['country']:
        order.country_id = payload['country']
    if payload.get('zip') and order.zip != payload['zip']:
        order.zip = payload['zip']
    if payload.get('shipping') and order.shipping_method_id != payload['shipping']:
        order.shipping_method_id = payload['shipping']
    if payload.get('phone') and order.phone != payload['phone']:
        order.phone = payload['phone']
    if payload.get('comment') and order.comment != payload['comment']:
        order.comment = payload['comment']
    if payload.get('attached_orders'):
        order.attach_orders(payload['attached_orders'])

def _update_suborder(order, order_products, suborder_data, errors):
    try:
        suborder = order.suborders.filter(and_(
            Suborder.order_id == order.id,
            Suborder.seq_num == suborder_data.get('seq_num')
        )).first()
        if suborder is None:
            _add_suborder(order, suborder_data, errors)
            db.session.flush()
        else:
            subcustomer, _state = parse_subcustomer(suborder_data['subcustomer'])
            suborder.buyout_date = datetime.strptime(suborder_data['buyout_date'], '%Y-%m-%d') \
                if suborder_data.get('buyout_date') else None
            suborder.subcustomer = subcustomer
            suborder_products = map_reduce(suborder_data['items'],
                keyfunc=lambda op: op['item_code'],
                valuefunc=lambda op: int(op['quantity']),
                reducefunc=sum
            )
            suborder_products = [{'item_code': i[0], 'quantity': i[1]} 
                                 for i in suborder_products.items()]
            if len(suborder_products) > 10:
                errors.append(f'The suborder for {subcustomer.name} has more than 10 products')
            for item in suborder_products:
                order_product = [op for op in suborder.order_products
                                    if op.product_id == item['item_code']]
                if len(order_product) > 0:
                    update_order_product(order, order_product[0], item)
                    try:
                        order_products.remove(order_product[0])
                    except ValueError:
                        current_app.logger.exception(
                            "Couldn't remove <OP: %s> from the list. Apparently it's not there anymore",
                            order_product[0].id)
                else:
                    try:
                        add_order_product(suborder, item, errors)
                    except Exception as ex:
                        current_app.logger.debug("Didn't add product: %s", ex)
            if suborder.buyout_date and (
                not order.purchase_date or order.purchase_date > suborder.buyout_date):
                order.set_purchase_date(suborder.buyout_date)
    except SubcustomerParseError:
        abort(Response(f"""Couldn't find subcustomer and provided data
                        doesn't allow to create new one. Please provide
                        new subcustomer data in format: 
                        <ID>, <Name>, <Password>
                        Erroneous data is: {suborder_data['subcustomer']}""",
                    status=400))

@bp_api_admin.route('/product/<int:order_product_id>', methods=['POST'])
@roles_required('admin')
def admin_save_order_product(order_product_id):
    '''
    Modifies order products
    Order product payload is received as JSON
    '''
    from app.orders.signals import order_product_saving
    payload = request.get_json()
    if not payload:
        return Response(status=304)
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"Order product ID={order_product_id} wasn't found", status=404))
    payload = cleanse_payload(order_product, payload)

    modify_object(order_product, payload, ['product_id', 'price', 'quantity',
                                           'private_comment', 'public_comment',
                                           'status'])
    order_product_saving.send(order_product, payload=payload)
    try:
        if order_product.need_to_update_total(payload):
            order_product.suborder.order.update_total()
        db.session.commit()
        return jsonify(order_product.to_dict())
    except NoShippingRateError:
        abort(Response(f"No shipping rate available", status=409))
    except Exception as ex:
        abort(Response(str(ex), status=500))

@bp_api_user.route('/product/<int:order_product_id>', methods=['DELETE'])
@login_required
def user_delete_order_product(order_product_id):
    '''Deletes selected order product'''
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"No order product <{order_product_id}> was found", status=404))

    order_product.delete()
    order_product.suborder.order.update_total()
    db.session.commit()

    return jsonify({
        'id': order_product_id,
        'status': 'success'
    })

@bp_api_admin.route('/product/<int:order_product_id>/status/<order_product_status>',
                   methods=['POST'])
@roles_required('admin')
def admin_set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"No order product <{order_product_id}> was found", status=404))

    order_product_status = OrderProductStatus[order_product_status]
    order_product.set_status(order_product_status, current_user)
    db.session.commit()

    return jsonify({
        'id': order_product_id,
        'order_product_status': order_product_status.name,
        'status': 'success'
    })

def add_order_product(suborder, item, errors):
    # with db.session.no_autoflush:
    try:
        product = Product.get_product_by_id(item['item_code'])
        if product:
            order_product = OrderProduct(
                suborder=suborder,
                product=product,
                price=product.price,
                quantity=int(item['quantity']),
                status=OrderProductStatus.pending)
            # db.session.add(order_product)
            suborder.order_products.append(order_product)
            suborder.order.total_weight += product.weight * order_product.quantity
            suborder.order.subtotal_krw += product.price * order_product.quantity
            return order_product
        raise ProductNotFoundError(item['item_code'])
    except Exception as ex:
        errors.append(ex.args)
        raise ex

@bp_api_user.route('/product/<int:order_product_id>/postpone', methods=['POST'])
@login_required
def postpone_order_product(order_product_id):
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"No product <{order_product_id}> was found", status=404))
    postponed_order_product = order_product.postpone()
    order_product.suborder.order.update_total()
    db.session.commit()
    
    return jsonify({
        'new_id': postponed_order_product.id,
        'new_suborder_id': postponed_order_product.suborder_id,
        'new_order_id': postponed_order_product.suborder.order_id,
        'status': 'success'
    })
    

def update_order_product(order, order_product, item):
    if order_product.quantity != int(item['quantity']):
        order_product.quantity = int(item['quantity'])
        order_product.when_changed = datetime.now()
        order.when_changed = datetime.now()

@bp_api_admin.route('/<order_id>', methods=['POST'])
@roles_required('admin')
def admin_save_order(order_id):
    '''
    Updates existing order
    Payload is provided in JSON
    '''
    logger = logging.getLogger(f'admin_save_order:{order_id}')
    order: Order = Order.query.get(order_id)
    if not order:
        abort(Response(f'No order {order_id} was found', status=404))
    with OrderEditValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't edit an order",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    payload = cleanse_payload(order, request.get_json())
    logger.info('Modifying order by %s with data: %s',
                current_user, payload)
    if payload.get('boxes'):
        update_order_boxes(order, payload['boxes'])
    if payload.get('total_weight'):
        order.total_weight = int(payload['total_weight'])
        order.total_weight_set_manually = True
    modify_object(order, payload, ['tracking_id', 'tracking_url'])
    if order.need_to_update_total(payload):
        order.update_total()
    if payload.get('status'):
        try:
            order.set_status(payload['status'], current_user)
        except UnfinishedOrderError as ex:
            logger.info(str(ex))
            abort(Response(str(ex), status=409))

    db.session.commit()
    return jsonify({'data': [order.to_dict()]})

def update_order_boxes(order, boxes_input):
    order.boxes = []
    for order_box in boxes_input:
        order.boxes.append(OrderBox(
            quantity=order_box['quantity'],
            weight=order_box['weight'],
            length=order_box['length'],
            width=order_box['width'],
            height=order_box['height']))

@bp_api_user.route('/product')
@bp_api_admin.route('/product')
@login_required
def get_order_products():
    '''
    Returns list of ordered items.
    '''
    order_products = OrderProduct.query
    if not current_user.has_role('admin'):
        order_products = order_products.filter(
            OrderProduct.suborder.has(
                Suborder.order.has(Order.user == current_user)))

    if request.values.get('order_id'):
        order_products = order_products.filter(or_(
            OrderProduct.order_id == request.values['order_id'],
            OrderProduct.suborder.has(Suborder.order_id == request.values['order_id'])))

    if request.values.get('draw') is not None: # Args were provided by DataTables
        filter_clause = f"%{request.values['search[value]']}%"
        order_products, records_total, records_filtered = prepare_datatables_query(
            order_products, request.values,
            or_(
                OrderProduct.suborder.has(Suborder.order_id.like(filter_clause)),
                OrderProduct.suborder.has(
                    Suborder.subcustomer.has(
                        Subcustomer.name.like(filter_clause))),
                OrderProduct.suborder.has(
                    Suborder.order.has(
                        Order.customer_name.like(filter_clause))),
                OrderProduct.product_id.like(filter_clause),
                OrderProduct.product.has(Product.name.like(filter_clause)),
                OrderProduct.product.has(Product.name_english.like(filter_clause)),
                OrderProduct.product.has(Product.name_russian.like(filter_clause)),
                OrderProduct.status == request.values['search[value]']
            )
        )
        outcome = [entry.to_dict() for entry in order_products]
        if not current_user.has_role('admin'):
            for entry in outcome:
                entry.pop('private_comment', None)
        return jsonify({
            'draw': request.values['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': outcome
        })
    order_products = order_products.limit(100)
    if order_products.count() == 0:
        abort(Response("No order products were fond", status=404))

    outcome = [entry.to_dict() for entry in order_products]
    if not current_user.has_role('admin'):
        for entry in outcome:
            entry.pop('private_comment', None)

    return jsonify(outcome)

@bp_api_user.route('/status')
@login_required
def user_get_order_statuses():
    return jsonify([i.name for i in OrderStatus])

@bp_api_user.route('/product/status')
@login_required
def user_get_order_product_statuses():
    return jsonify([i.name for i in OrderProductStatus])

@bp_api_user.route('/product/<int:order_product_id>/status/history')
@login_required
def user_get_order_product_status_history(order_product_id):
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"No order product <{order_product_id}> was found", status=404))

    return jsonify([entry.to_dict() for entry in order_product.status_history])


def get_order_product(order_product_id):
    order_product = OrderProduct.query
    if not current_user.has_role('admin'):
        order_product = order_product.filter(OrderProduct.suborder.has(
            Suborder.order.has(Order.user == current_user)))
    order_product = order_product.filter_by(id=order_product_id).first()
    return order_product

@bp_api_user.route('/<order_id>/excel')
@login_required
def user_get_order_excel(order_id):
    '''
    Generates an Excel file for an order
    '''
    order = Order.query.get(order_id)
    if not order:
        abort(Response(f"The order <{order_id}> was not found", status=404))
    try:
        file = order.get_order_excel()
        return current_app.response_class(stream_and_close(file), headers={
            'Content-Disposition': f'attachment; filename="{order_id}.xlsx"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
    except OrderError as ex:
        abort(Response(
            f"Couldn't generate an order Excel due to following error: {';'.join(ex.args)}"))

@bp_api_admin.route('/<order_id>/box')
@roles_required('admin')
def admin_get_order_boxes(order_id):
    order = Order.query.get(order_id)
    if order is None:
        abort(Response(f"No order <{order_id}> found", status=404))
    return jsonify([box.to_dic() for box in order.boxes])
