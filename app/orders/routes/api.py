'''API endpoints for sale order management'''
from app.orders.models.order import OrderBox
from datetime import datetime
from more_itertools import map_reduce
import re

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from sqlalchemy import and_, not_, or_
from sqlalchemy.exc import IntegrityError, OperationalError, DataError

from app import db
from app.exceptions import AtomyLoginError, EmptySuborderError, NoShippingRateError, \
    OrderError, SubcustomerParseError, ProductNotFoundError, UnfinishedOrderError
from app.models import Country
from app.orders import bp_api_admin, bp_api_user
from app.orders.models import Order, OrderProduct, OrderProductStatus, \
    OrderStatus, Suborder, Subcustomer
from app.orders.validators.order import OrderEditValidator, OrderValidator
from app.products.models import Product
from app.shipping.models import Shipping, PostponeShipping
from app.users.models.user import User
from app.utils.atomy import atomy_login
from app.tools import prepare_datatables_query, modify_object, stream_and_close

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
        'data': list(map(lambda entry: entry.to_dict(), orders))
    })

def _set_draft(order):
    draft_order_id_prefix = f'ORD-draft-{current_user.id}-'
    if not order.id.startswith(draft_order_id_prefix):
        last_draft = Order.query \
            .filter(Order.id.startswith(draft_order_id_prefix)) \
            .order_by(Order.id.desc()).first()
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

        order.attach_orders(payload.get('attached_orders'))
        db.session.add(order)
        # order_products = []
        errors = []
        # ordertotal_weight = 0
        add_suborders(order, payload['suborders'], errors)
        try:
            order.update_total()
        except NoShippingRateError:
            abort(Response("No shipping rate available", status=409))

    try:
        # db.session.commit()
        db.session.commit()
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

def add_suborders(order, suborders, errors):
    suborders_count = 0
    for suborder_data in suborders:
        suborder_data_subset = suborder_data.copy()
        for index in range(0, len(suborder_data['items']), 10):
            suborder_data_subset['items'] = suborder_data['items'][index:index + 10]
            try:
                add_suborder(order, suborder_data_subset, errors)
                db.session.flush()
                suborders_count += 1
            except EmptySuborderError as ex:
                errors.append(f"Suborder for <{ex.args[0]}> is empty. Skipped")
    if suborders_count == 0:
        abort(Response("The order is empty. Please add at least one product.", status=409))

def add_suborder(order, suborder_data, errors):
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
        current_app.logger.debug("Order %s suborders count is %s", order.id, order.suborders.count())
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

def parse_subcustomer(subcustomer_data):
    '''Returns a tuple of customer from raw data
    and indication whether customer is existing one or created'''
    parts = subcustomer_data.split(',')
    try:
        subcustomer = Subcustomer.query.filter(
            Subcustomer.username == parts[0].strip()).first()
        if subcustomer:
            if len(parts) >= 2 and subcustomer.name != parts[1].strip():
                subcustomer.name = parts[1].strip()
            if len(parts) == 3 and subcustomer.password != parts[2].strip():
                subcustomer.password = parts[2].strip()
            return subcustomer, False
    except DataError as ex:
        message = ex.orig.args[1]
        match = re.search('(INSERT INTO|UPDATE) (.+?) ', ex.statement)
        if match:
            table = match.groups()[1]
            if table:
                if table == 'subcustomers':
                    message = "Subcustomer error: " + message + " " + str(ex.params[2:5])
            result = {
                'status': 'error',
                'message': f"""Couldn't parse the subcustomer due to input error. Check your form and try again.
                            {message}"""
            }
    except IndexError:
        pass # the password wasn't provided, so we don't update
    try:
        subcustomer = Subcustomer(
            username=parts[0].strip(),
            name=parts[1].strip(),
            password=parts[2].strip(),
            when_created=datetime.now())
        # db.session.add(subcustomer)
        return subcustomer, True
    except ValueError as ex:
        raise SubcustomerParseError(str(ex))
    except IndexError:
        raise SubcustomerParseError("The subcustomer string doesn't conform <ID, Name, Password> format")

@bp_api_user.route('/<order_id>', methods=['POST'])
@login_required
def user_save_order(order_id):
    ''' Updates existing order '''
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
            add_suborder(order, suborder_data, errors)
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
def save_order_product(order_product_id):
    '''
    Modifies order products
    Order product payload is received as JSON
    '''
    payload = request.get_json()
    if not payload:
        return Response(status=304)
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"Order product ID={order_product_id} wasn't found", status=404))

    editable_attributes = ['product_id', 'price', 'quantity', 'subcustomer',
                           'private_comment', 'public_comment', 'status']
    for attr in editable_attributes:
        if payload.get(attr):
            setattr(order_product, attr, payload[attr])
            order_product.when_changed = datetime.now()
    try:
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
    logger = current_app.logger.getChild('admin_save_order')
    order_input = request.get_json()
    order = Order.query.get(order_id)
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
    logger.info('Modifying order %s by %s with data: %s',
                order_id, current_user, order_input)
    if order_input.get('boxes'):
        update_order_boxes(order, order_input['boxes'])
    if order_input.get('total_weight'):
        order.total_weight = int(order_input['total_weight'])
        order.total_weight_set_manually = True
    modify_object(order, order_input, ['tracking_id', 'tracking_url'])
    order.update_total()
    if order_input.get('status'):
        try:
            order.set_status(order_input['status'], current_user)
        except UnfinishedOrderError as ex:
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
        outcome = list(map(lambda entry: entry.to_dict(), order_products))
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

    outcome = list(map(lambda entry: entry.to_dict(), order_products))
    if not current_user.has_role('admin'):
        for entry in outcome:
            entry.pop('private_comment', None)

    return jsonify(outcome)

@bp_api_user.route('/status')
@login_required
def user_get_order_statuses():
    return jsonify(list(map(lambda i: i.name, OrderStatus)))

@bp_api_user.route('/product/status')
@login_required
def user_get_order_product_statuses():
    return jsonify(list(map(lambda i: i.name, OrderProductStatus)))

@bp_api_user.route('/product/<int:order_product_id>/status/history')
@login_required
def user_get_order_product_status_history(order_product_id):
    order_product = get_order_product(order_product_id)
    if not order_product:
        abort(Response(f"No order product <{order_product_id}> was found", status=404))

    return jsonify(list(map(lambda entry: entry.to_dict(), order_product.status_history)))

@bp_api_admin.route('/subcustomer')
@roles_required('admin')
def admin_get_subcustomers():
    subcustomers = Subcustomer.query
    if request.values.get('draw') is not None: # Args were provided by DataTables
        filter_clause = f"%{request.values['search[value]']}%"
        subcustomers, records_total, records_filtered = prepare_datatables_query(
            subcustomers, request.values,
            or_(
                Subcustomer.name.like(filter_clause),
                Subcustomer.username.like(filter_clause)
            )
        )
        outcome = list(map(lambda entry: entry.to_dict(), subcustomers))

        return jsonify({
            'draw': request.values['draw'],
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': outcome
        })
    if request.values.get('initialValue') is not None:
        sub = Subcustomer.query.get(request.values.get('value'))
        return jsonify(
            {'id': sub.id, 'text': sub.name} \
                if sub is not None else {})
    if request.values.get('q') is not None:
        subcustomers = subcustomers.filter(or_(
            Subcustomer.name.like(f'%{request.values["q"]}%'),
            Subcustomer.username.like(f'%{request.values["q"]}%')
        ))
    if request.values.get('page') is not None:
        page = int(request.values['page'])
        total_results = subcustomers.count()
        subcustomers = subcustomers.offset((page - 1) * 100).limit(page * 100)
        return jsonify({
            'results': [entry.to_dict() for entry in subcustomers],
            'pagination': {
                'more': total_results > page * 100
            }
        })
    return jsonify([entry.to_dict() for entry in subcustomers])

@bp_api_admin.route('/subcustomer', methods=['POST'])
@roles_required('admin')
def admin_create_subcustomer():
    payload = request.get_json()
    if payload is None:
        abort(Response("No customer data is provided", status=400))
    try:
        if Subcustomer.query.filter_by(username=payload['username']).first():
            abort(Response("Subcustomer with such username already exists", status=409))
        subcustomer = Subcustomer(
            name=payload['name'],
            username=payload['username'],
            password=payload['password']
        )
        db.session.add(subcustomer)
        db.session.commit()
        return jsonify(subcustomer.to_dict())
    except KeyError:
        abort(Response("Not all subcustomer data is provided", status=400))
    
@bp_api_admin.route('/subcustomer/<subcustomer_id>', methods=['POST'])
@roles_required('admin')
def admin_save_subcustomer(subcustomer_id):
    payload = request.get_json()
    if payload is None:
        abort(Response("No customer data is provided", status=400))
    subcustomer = Subcustomer.query.get(subcustomer_id)
    if subcustomer is None:
        abort(Response(f"No customer <{subcustomer_id}> is found", status=404))

    if payload.get('username') and \
        Subcustomer.query.filter_by(username=payload['username']).count() > 0:
        abort(Response(
            f"Subcustomer with username <{payload['username']}> already exists",
            status=409))
    modify_object(subcustomer, payload, ['name', 'username', 'password', 'in_network'])
    db.session.commit()
    return jsonify(subcustomer.to_dict())

@bp_api_admin.route('/subcustomer/<subcustomer_id>', methods=['DELETE'])
@roles_required('admin')
def admin_delete_subcustomer(subcustomer_id):
    subcustomer = Subcustomer.query.get(subcustomer_id)
    if subcustomer is None:
        abort(Response(f"No customer <{subcustomer_id}> is found", status=404))
    owned_suborders = Suborder.query.filter_by(subcustomer=subcustomer)
    if owned_suborders.count() > 0:
        suborder_ids = ','.join([s.id for s in owned_suborders])
        abort(Response(
            f"Can't delete subcustomer that has suborders: {suborder_ids}", status=409))
    db.session.delete(subcustomer)
    db.session.commit()
    return jsonify({'status': 'success'})


@bp_api_user.route('/subcustomer/validate', methods=['POST'])
@login_required
def validate_subcustomer():
    payload = request.get_json()
    if not payload or not payload.get('subcustomer'):
        abort(Response('No subcustomer data was provided', status=400))
    
    current_app.logger.debug(f"Validating subcustomer {payload}")
    try:
        subcustomer, _is_new = parse_subcustomer(payload['subcustomer'])
        atomy_login(subcustomer.username, subcustomer.password, run_browser=False)
        return jsonify({'result': 'success'})
    except SubcustomerParseError as ex:
        return jsonify({'result': 'failure', 'message': str(ex)})
    except AtomyLoginError:
        current_app.logger.info("Couldn't validate subcustomer %s", payload)
        return jsonify({'result': 'failure'})

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
