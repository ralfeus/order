'''
Contains api endpoint routes of the application
'''
from datetime import datetime
from functools import reduce
from more_itertools import map_reduce
import openpyxl
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, Response, abort, jsonify, request, send_file
from flask_security import current_user, login_required, roles_required

from app import db
from app.models import \
    Currency, Invoice, Order, OrderProduct, OrderProductStatusEntry, Product, \
    User, Transaction, TransactionStatus

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')

@admin_api.route('/order_product')
@login_required
@roles_required('admin')
def get_order_products():
    '''
    Returns list of ordered items. So far implemented only for admins
    '''
    order_products_query = OrderProduct.query
    if request.values.get('order_id'):
        order_products_query = order_products_query.filter_by(order_id=request.values['order_id'])

    return jsonify(list(map(lambda order_product: order_product.to_dict(), order_products_query.all())))

@admin_api.route('/order_product/<int:order_product_id>', methods=['POST'])
@login_required
@roles_required('admin')
def save_order_product(order_product_id):
    '''
    Modifies order products
    '''
    result = None
    payload = request.get_json()
    order_product = OrderProduct.query.get(order_product_id)
    if order_product:
        if payload and payload.get('private_comment'):
            order_product.private_comment = payload['private_comment']
        order_product.public_comment = payload['public_comment']
        order_product.changed_at = datetime.now()
        try:
            db.session.commit()
            result = jsonify({
                'order_id': order_product.order_id,
                'order_product_id': order_product.id,
                'customer': order_product.order.name,
                'subcustomer': order_product.subcustomer,
                'product_id': order_product.product_id,
                'product': order_product.product.name_english,
                'private_comment': order_product.private_comment,
                'public_comment': order_product.public_comment,
                'quantity': order_product.quantity,
                'status': order_product.status
            })
        except Exception as e:
            result = jsonify({
                'status': 'error',
                'message': e
            })
            result.status_code = 500
    else:
        result = jsonify({
            'status': 'error',
            'message': f"Order product ID={order_product_id} wasn't found"
        })
        result.status_code = 404
    return result


@admin_api.route('/order_product/<int:order_product_id>/status/<order_product_status>', methods=['POST'])
@roles_required('admin')
def admin_set_order_product_status(order_product_id, order_product_status):
    '''
    Sets new status of the selected order product
    '''
    order_product = OrderProduct.query.get(order_product_id)
    order_product.status = order_product_status
    db.session.add(OrderProductStatusEntry(
        order_product=order_product,
        status=order_product_status,
        # set_by=current_user,
        user_id=1,
        set_at=datetime.now()
    ))

    db.session.commit()

    return jsonify({
        'order_product_id': order_product_id,
        'order_product_status': order_product_status,
        'status': 'success'
    })

@admin_api.route('/order_product/<int:order_product_id>/status/history')
@roles_required('admin')
def admin_get_order_product_status_history(order_product_id):
    history = OrderProductStatusEntry.query.filter_by(order_product_id=order_product_id)
    if history:
        return jsonify(list(map(lambda entry: {
            'set_by': entry.set_by.username,
            'set_at': entry.set_at,
            'status': entry.status
        }, history)))
    else:
        result = jsonify({
            'status': 'error',
            'message': f'No order product ID={order_product_id} found'
        })
        result.status_code = 404
        return result

@admin_api.route('/product', defaults={'product_id': None})
@admin_api.route('/product/<product_id>')
@roles_required('admin')
def admin_get_product(product_id):
    '''
    Returns list of products in JSON:
        {
            'id': product ID,
            'name': product original name,
            'name_english': product english name,
            'name_russian': product russian name,
            'price': product price in KRW,
            'weight': product weight,
            'points': product points
        }
    '''
    product_query = None
    if product_id:
        product_query = Product.query.filter_by(id=product_id)
    else:
        product_query = Product.query.all()
    return jsonify(Product.get_products(product_query))

@admin_api.route('/product', methods=['POST'])
@roles_required('admin')
def save_product():
    '''
    Saves updates in product or creates new product
    '''
    product_input = request.get_json()
    product = Product.query.get(product_input['id'])
    if not product:
        product = Product()
    product.name = product_input['name']
    product.name_english = product_input['name_english']
    product.name_russian = product_input['name_russian']
    product.price = product_input['price']
    product.points = product_input['points']
    product.weight = product_input['weight']
    product.available = product_input['available']
    if not product.id:
        db.session.add(product)
    db.session.commit()

    return jsonify({
        'status': 'success'
    })

@admin_api.route('/product/<product_id>', methods=['DELETE'])
@roles_required('admin')
def delete_product(product_id):
    '''
    Deletes a product by its product code
    '''
    result = None
    try:
        Product.query.filter_by(id=product_id).delete()
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete product {product_id} as it's used in some orders"
        })
        result.status_code = 409

    return result

@admin_api.route('/transaction', defaults={'transaction_id': None})
@admin_api.route('/transaction/<int:transaction_id>')
@roles_required('admin')
def admin_get_transactions(transaction_id):
    '''
    Returns all or selected transactions in JSON:
    {
        id: transaction ID,
        user_id: ID of the transaction owner,
        currency: transaction original currency,
        amount_original: amount in original currency,
        amount_krw: amount in KRW at the time of transaction,
        status: transaction status ('pending', 'approved', 'rejected', 'cancelled')
    }
    '''
    transactions = Transaction.query.all() \
        if transaction_id is None \
        else Transaction.query.filter_by(id=transaction_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), transactions)))

@admin_api.route('/transaction/<int:transaction_id>', methods=['POST'])
@roles_required('admin')
def admin_save_transaction(transaction_id):
    '''
    Saves updates in user profile.
    '''
    payload = request.get_json()
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        abort(404)
    if transaction.status in (TransactionStatus.approved, TransactionStatus.cancelled):
        abort(Response(f"Can't update transaction in state <{transaction.status}>", status=409))
    if payload:
        if payload.get('amount_original'):
            transaction.amount_sent_original = payload['amount_original']
        if payload.get('currency_code'):
            transaction.currency = Currency.query.get(payload['currency_code'])
        if payload.get('amount_krw'):
            transaction.amount_sent_krw = payload['amount_krw']
        if payload.get('amount_received_krw'):
            transaction.amount_received_krw = payload['amount_received_krw']
        if payload.get('status') and transaction.status != TransactionStatus.approved:
            transaction.status = payload['status'].lower()
    else:
        abort(400)
    transaction.when_changed = datetime.now()
    transaction.changed_by = current_user

    db.session.commit()

    return jsonify(transaction.to_dict())

@admin_api.route('/user/<user_id>', methods=['DELETE'])
@roles_required('admin')
def delete_user(user_id):
    '''
    Deletes a user by its user_id
    '''
    result = None
    try:
        User.query.filter_by(id=user_id).delete(synchronize_session='fetch')
        db.session.commit()
        result = jsonify({
            'status': 'success'
        })
    except IntegrityError:
        result = jsonify({
            'message': f"Can't delete user {user_id} as it's used in some orders"
        })
        result.status_code = 409

    return result
        
@admin_api.route('/user/<int:user_id>', methods=['POST'])
@roles_required('admin')
def save_user(user_id):    
    user_input = request.get_json()
    user = User.query.get(user_id)
    if not user:
        user = User()

    if user_input.get('username') is not None:
        user.username = user_input['username']
    
    if user_input.get('email') is not None:
        user.email = user_input['email']

    if user_input.get('password') is not None:
        user.password = user_input['password']

    if user_input.get('enabled') is not None:
        user.enabled = user_input['enabled']

    if not user.id:
        db.session.add(user)

    user.when_changed = datetime.now()

    db.session.commit()
    return jsonify(user.to_dict())

@admin_api.route('/invoice', defaults={'invoice_id': None})
@admin_api.route('/invoice/<invoice_id>')
@roles_required('admin')
def admin_get_invoices(invoice_id):
    '''
    Returns all or selected invoices in JSON:
    {
        id: invoice ID,
        [
            order_product_id: ID of the order product,
            name: name of the order product,
            quantity: quantity of order product,
            amount_krw: amount in KRW
        ]
    }
    '''
    invoices = Invoice.query.all() \
        if invoice_id is None \
        else Invoice.query.filter_by(id=invoice_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), invoices)))

@admin_api.route('/invoice/new', methods=['POST'])
@roles_required('admin')
def admin_create_invoice():
    '''
    Creates invoice for provided orders
    '''
    payload = request.get_json()
    if not payload or not payload['order_ids']:
        abort(Response("No orders were provided", status=400))
    orders = Order.query.filter(Order.id.in_(payload['order_ids'])).all()
    if not orders:
        abort(Response("No orders with provided IDs were found ", status=400))
    invoice = Invoice()
    invoice.when_created = datetime.now()
    for order in orders:
        order.invoice = invoice

    db.session.add(invoice)
    db.session.commit()
    return jsonify({
        'status': 'success',
        'invoice_id': invoice.id
    })

def get_invoice_order_products(invoice, usd_rate):
    order_products = map_reduce(
        [order_product for order in invoice.orders
            for order_product in order.order_products],
        keyfunc=lambda op: (
            op.product_id,
            op.product.name_english if op.product.name_english \
                else op.product.name,
            op.price * usd_rate),
        valuefunc=lambda op: op.quantity,
        reducefunc=sum
    )
    result = list(map(lambda op: {
        'id': op[0][0],
        'name': op[0][1],
        'price': op[0][2],
        'quantity': op[1],
        'subtotal': op[0][2] * op[1]
    }, order_products.items()))
    return result

def create_invoice_excel(reference_invoice, invoice_file_name, usd_rate):
    invoice_wb = openpyxl.open('app/static/invoices/invoice_template.xlsx')
    invoice_dict = reference_invoice.to_dict()
    order_products = get_invoice_order_products(reference_invoice, usd_rate)
    ws = invoice_wb.worksheets[0]
    pl = invoice_wb.worksheets[1]

    # Set invoice header
    ws.cell(7, 2, reference_invoice.id)
    ws.cell(7, 5, reference_invoice.when_created)
    ws.cell(13, 4, reference_invoice.orders[0].name)
    ws.cell(17, 4, reference_invoice.orders[0].address)
    ws.cell(21, 4, '') # city
    ws.cell(23, 5, reference_invoice.orders[0].country)
    ws.cell(25, 4, reference_invoice.orders[0].phone)

    # Set packing list header
    pl.cell(7, 2, reference_invoice.id)
    pl.cell(7, 5, reference_invoice.when_created)
    pl.cell(13, 4, reference_invoice.orders[0].name)
    pl.cell(17, 4, reference_invoice.orders[0].address)
    pl.cell(21, 4, '') # city
    pl.cell(23, 5, reference_invoice.orders[0].country)
    pl.cell(25, 4, reference_invoice.orders[0].phone)

    # Set invoice footer
    ws.cell(305, 5, invoice_dict['total'] * usd_rate)
    ws.cell(311, 4, f"{round(invoice_dict['total'] * usd_rate, 2)} USD")
    ws.cell(312, 2, invoice_dict['weight'] / 1000)

    # Set packing list footer
    pl.cell(311, 4, f"{reduce(lambda qty, op: qty + op['quantity'], order_products, 0)}psc")
    pl.cell(312, 2, invoice_dict['weight'] / 1000)

    # Set order product lines
    row = 31
    last_row = 304

    for op in order_products:
        # Set invoice product item
        ws.cell(row, 1, op['id'])
        ws.cell(row, 2, op['name'])
        ws.cell(row, 3, op['quantity'])
        ws.cell(row, 4, op['price'])
        ws.cell(row, 5, op['subtotal'])

        # Set packing list product item
        pl.cell(row, 1, op['id'])
        pl.cell(row, 2, op['name'])
        pl.cell(row, 4, op['quantity'])

        row += 1
    ws.delete_rows(row, last_row - row + 1)
    pl.delete_rows(row, last_row - row + 1)
    invoice_wb.save(f'app/static/invoices/{invoice_file_name}')

@admin_api.route('/invoice/<invoice_id>/excel/<float:usd_rate>')
@roles_required('admin')
def get_invoice_excel(invoice_id, usd_rate):
    '''
    Generates an Excel file for an invoice
    '''
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(404)
    create_invoice_excel(
        reference_invoice=invoice, invoice_file_name=f'{invoice_id}.xlsx', 
        usd_rate=usd_rate)

    return send_file(f'static/invoices/{invoice_id}.xlsx',
                     as_attachment=True, attachment_filename=invoice_id + '.xlsx')

@admin_api.route('/invoice/excel/<float:usd_rate>')
@roles_required('admin')
def get_invoice_cumulative_excel(usd_rate):
    '''
    Returns cumulative Excel of several invoices
    invoice IDs are provides as URL arguments
    Resulting Excel isn't saved anywhere
    '''
    cumulative_invoice = Invoice()
    for invoice_id in request.args.getlist('invoices'):
        invoice = Invoice.query.get(invoice_id)
        cumulative_invoice.orders += invoice.orders

    invoice_file_name = 'cumulative_invoice.xlsx'
    create_invoice_excel(
        reference_invoice=cumulative_invoice,
        invoice_file_name=invoice_file_name, usd_rate=usd_rate)
    return send_file(f'static/invoices/{invoice_file_name}',
        as_attachment=True, attachment_filename=invoice_file_name)

@admin_api.route('/order', defaults={'order_id': None})
@admin_api.route('/order/<order_id>')
@roles_required('admin')
def get_orders(order_id):
    '''
    Returns all or selected orders in JSON:
    {
        id: invoice ID,
        [
            user: username of order creator,
            name: name of the customer,
            total: total amount in KRW,
            when_created: time of the order creation
        ]
    }
    '''
    orders = Order.query.all() \
        if order_id is None \
        else Order.query.filter_by(id=order_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), orders)))
