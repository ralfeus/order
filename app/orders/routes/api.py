from datetime import datetime
import re

from flask import Response, abort, current_app, jsonify, request
from flask_security import current_user, login_required, roles_required

from sqlalchemy import and_, or_, not_
from sqlalchemy.exc import IntegrityError, OperationalError, DataError

from app import db
from app.exceptions import SubcustomerParseError
from app.models import Country, User
from app.orders import bp_api_admin, bp_api_user
from app.orders.models import Order, OrderProduct, OrderProductStatus, \
    OrderStatus, Suborder, Subcustomer
from app.products.models import Product
from app.shipping.models import Shipping, PostponeShipping
from app.utils.atomy import atomy_login
from app.tools import prepare_datatables_query, modify_object

@bp_api_admin.route('/<order_id>', methods=['DELETE'])
@roles_required('admin')
def delete_order(order_id):
    '''
    Deletes specified order
    '''
    order = Order.query.get(order_id)
    if order is None:
        abort(Response(f"No order <{order_id}> was found", status=404))
    if order.status in [OrderStatus.paid, OrderStatus.po_created, OrderStatus.shipped]:
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
        order_id, order.name, order.when_created, current_user.username)
    return Response(status=200)
        

@bp_api_admin.route('', defaults={'order_id': None})
@bp_api_admin.route('/<order_id>')
@roles_required('admin')
def admin_get_orders(order_id):
    '''
    Returns all or selected orders in JSON
    '''
    orders = Order.query
    if order_id is not None:
        orders = orders.filter_by(id=order_id)
        if orders.count() == 1:
            return jsonify(orders.first().to_dict(details=True))
    if request.values.get('status'):
        orders = orders.filter_by(status=OrderStatus[request.values['status']].name)
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return filter_orders(orders, request.values)

    if orders.count() == 0:
        abort(Response("No orders were found", status=404))
    else:
        return jsonify(list(map(
            lambda entry: entry.to_dict(details=request.values.get('details')), orders)))

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
            not_(Order.status.in_([OrderStatus.shipped, OrderStatus.complete])))
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return filter_orders(orders, request.values)
    if orders.count() == 0:
        abort(Response("No orders were found", status=404))
    else:
        return jsonify(list(map(
            lambda entry: entry.to_dict(details=request.values.get('details')), orders)))

def filter_orders(orders, filter_params):
    orders = orders.order_by(Order.purchase_date_sort)
    orders, records_total, records_filtered = prepare_datatables_query(
        orders, filter_params, or_(
            Order.id.like(f"%{filter_params['search[value]']}%"),
            Order.user.has(User.username.like(f"%{filter_params['search[value]']}%")),
            Order.name.like(f"%{filter_params['search[value]']}%"),
            Order.status == filter_params['search[value]']
        )
    )
    return jsonify({
        'draw': filter_params['draw'],
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': list(map(lambda entry: entry.to_dict(), orders))
    })


@bp_api_user.route('', methods=['POST'])
@login_required
def user_create_order():
    '''
    Creates order.
    Accepts order details in payload
    Returns JSON
    '''
    request_data = request.get_json()
    if not request_data:
        abort(Response("No data is provided", status=400))
    result = {}
    shipping = Shipping.query.get(request_data['shipping'])
    country = Country.query.get(request_data['country'])
    if not country:
        abort(Response(f"The country <{request_data['country']}> was not found", status=400))
    order = Order(
        user=current_user,
        name=request_data['name'],
        address=request_data['address'],
        country_id=request_data['country'],
        country=country,
        shipping=shipping,
        phone=request_data['phone'],
        comment=request_data['comment'],
        subtotal_krw=0,
        status=OrderStatus.pending,
        when_created=datetime.now()
    )
    order.attach_orders(request_data.get('attached_orders'))
    db.session.add(order)
    # order_products = []
    errors = []
    # ordertotal_weight = 0
    add_suborders(order, request_data['suborders'], errors)

    try:
        order.update_total()
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
                           {str(ex)}"""
        }
    return jsonify(result)

def add_suborders(order, suborders, errors):
    for suborder_data in suborders:
        try:
            subcustomer, is_new = parse_subcustomer(suborder_data['subcustomer'])
            if is_new:
                db.session.add(subcustomer)
            suborder = Suborder(
                order=order,
                seq_num=suborder_data.get('seq_num'),
                subcustomer=subcustomer,
                buyout_date=datetime.strptime(suborder_data['buyout_date'], '%Y-%m-%d') \
                    if suborder_data.get('buyout_date') else None,
                local_shipping=0,
                when_created=datetime.now()
            )
            if suborder.buyout_date:
                if not order.purchase_date or order.purchase_date > suborder.buyout_date:
                    order.purchase_date = suborder.buyout_date

            current_app.logger.debug('Created instance of Suborder %s', suborder)
            db.session.add(suborder)
        except SubcustomerParseError:
            abort(Response(f"""Couldn't find subcustomer and provided data
                            doesn't allow to create new one. Please provide
                            new subcustomer data in format: 
                            <ID>, <Name>, <Password>
                            Erroneous data is: {suborder_data['subcustomer']}""",
                        status=400))

        for item in suborder_data['items']:
            try:
                add_order_product(suborder, item, errors)
            except:
                # current_app.logger.exception("Couldn't add product %s", item['item_code'])
                pass

def parse_subcustomer(subcustomer_data) -> (Subcustomer, bool):
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
    '''
    Updates existing order
    '''
    order = Order.query.get(order_id) if 'admin' in current_user.roles \
        else Order.query.filter_by(id=order_id, user=current_user).first()
    if not order:
        abort(Response(f"No order <{order_id}> was found", status=404))
    payload = request.get_json()
    if not payload:
        abort(Response("No order data was provided", status=400))

    errors = []
    if payload.get('name') and order.name != payload['name']:
        order.name = payload['name']
    if payload.get('address') and order.address != payload['address']:
        order.customer = payload['address']
    if payload.get('country') and order.country_id != payload['country']:
        order.country_id = payload['country']
    if payload.get('shipping') and order.shipping_method_id != payload['shipping']:
        order.shipping_method_id = payload['shipping']
    if payload.get('phone') and order.phone != payload['phone']:
        order.phone = payload['phone']
    if payload.get('comment') and order.comment != payload['comment']:
        order.comment = payload['comment']
    if payload.get('attached_orders'):
        order.attach_orders(payload['attached_orders'])

    # Edit or add order products
    if payload.get('suborders'):
        order_products = list(order.order_products)
        for suborder_data in payload['suborders']:
            try:
                suborder = order.suborders.filter(and_(
                    Suborder.order_id == order.id,
                    Suborder.seq_num == suborder_data['seq_num']    
                )).first()

                subcustomer, state = parse_subcustomer(suborder_data['subcustomer'])
                suborder.buyout_date = datetime.strptime(suborder_data['buyout_date'], '%Y-%m-%d') \
                    if suborder_data.get('buyout_date') else None
                suborder.subcustomer = subcustomer
                for item in suborder_data['items']:
                    order_product = [op for op in suborder.order_products
                                        if op.product_id == item['item_code']]
                    if len(order_product) > 0:
                        update_order_product(order, order_product[0], item)
                        order_products.remove(order_product[0])
                    else:
                        try:
                            add_order_product(suborder, item, errors)
                        except:
                            pass
                if suborder.buyout_date and (
                    not order.purchase_date or order.purchase_date > suborder.buyout_date):
                        order.purchase_date = suborder.buyout_date
            except SubcustomerParseError:
                abort(Response(f"""Couldn't find subcustomer and provided data
                                doesn't allow to create new one. Please provide
                                new subcustomer data in format: 
                                <ID>, <Name>, <Password>
                                Erroneous data is: {suborder_data['subcustomer']}""",
                            status=400))
    
        # Remove order products
        for order_product in order_products:
            delete_order_product(order, order_product)

    order.update_total()

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
    order_product = OrderProduct.query.get(order_product_id)
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
    except Exception as ex:
        abort(Response(str(ex), status=500))

@bp_api_user.route('/product/<int:order_product_id>/status/<order_product_status>',
                   methods=['POST'])
@login_required
def user_set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    order_product = OrderProduct.query
    if not current_user.has_role('admin'):
        order_product = order_product.filter(OrderProduct.suborder.has(
            Suborder.order.has(Order.user == current_user)))
    order_product = order_product.filter_by(id=order_product_id).first()
    if not order_product:
        abort(Response(f"No order product <{order_product_id}> was found", status=404))

    user_allowed_statuses = [OrderProductStatus.cancelled]
    order_product_status = OrderProductStatus[order_product_status]
    if not current_user.has_role('admin') \
        and order_product_status not in user_allowed_statuses:
        abort(Response(f"You are not allowed to set status <{order_product_status}>",
            status=409
        ))
    order_product.set_status(order_product_status, current_user)
    db.session.commit()

    return jsonify({
        'order_product_id': order_product_id,
        'order_product_status': order_product_status.name,
        'status': 'success'
    })

def add_order_product(suborder, item, errors):
    with db.session.no_autoflush:
        product = Product.get_product_by_id(item['item_code'])
        if product:
            order_product = OrderProduct(
                suborder=suborder,
                product=product,
                price=product.price,
                quantity=int(item['quantity']),
                status=OrderProductStatus.pending)
            db.session.add(order_product)
            suborder.order.total_weight += product.weight * order_product.quantity
            suborder.order.subtotal_krw += product.price * order_product.quantity
            return order_product

        errors.append(f'{item["item_code"]}: no such product')
        raise Exception(f'{item["item_code"]}: no such product')

def update_order_product(order, order_product, item):
    if order_product.quantity != int(item['quantity']):
        order_product.quantity = int(item['quantity'])
        order_product.when_changed = datetime.now()
        order.when_changed = datetime.now()

def delete_order_product(order, order_product):
    db.session.delete(order_product)
    order.total_weight -= order_product.product.weight * order_product.quantity
    order.subtotal_krw -= order_product.price * order_product.quantity
    order.when_changed = datetime.now()

@bp_api_admin.route('/<order_id>', methods=['POST'])
@roles_required('admin')
def admin_save_order(order_id):
    '''
    Updates existing order
    Payload is provided in JSON
    '''
    order_input = request.get_json()
    order = Order.query.get(order_id)
    if not order:
        abort(Response(f'No order {order_id} was found', status=404))

    if order_input.get('status') is not None:
        order.status = order_input['status']

    if order_input.get('tracking_id') is not None:
        order.tracking_id = order_input['tracking_id']

    if order_input.get('tracking_url') is not None:
        order.tracking_url = order_input['tracking_url']

    order.when_changed = datetime.now()

    db.session.commit()
    return jsonify(order.to_dict())

@bp_api_user.route('/product')
@bp_api_admin.route('/product')
@login_required
def get_order_products():
    '''
    Returns list of ordered items. So far implemented only for admins
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
                        Order.name.like(filter_clause))),
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
    order_product = OrderProduct.query
    if not current_user.has_role('admin'):
        order_product = order_product.filter(OrderProduct.suborder.has(
            Suborder.order.has(Order.user == current_user)))
    order_product = order_product.filter_by(id=order_product_id).first()
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
    
    return jsonify(list(map(lambda entry: entry.to_dict(), subcustomers)))

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
    modify_object(subcustomer, payload, ['name', 'username', 'password'])
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
    
    try:
        subcustomer, _is_new = parse_subcustomer(payload['subcustomer'])
        atomy_login(subcustomer.username, subcustomer.password)
        return jsonify({'result': 'success'})
    except SubcustomerParseError as ex:
        return jsonify({'result': 'failure', 'message': str(ex)})
    except:
        current_app.logger.exception("Couldn't validate subcustomer %s", payload)
        return jsonify({'result': 'failure'})
