from datetime import datetime
from functools import reduce
from more_itertools import map_reduce
import openpyxl

from flask import Response, abort, jsonify, request, send_file
from flask_security import roles_required

from app import db
from app.invoices import bp_api_admin, bp_api_user
from app.invoices.models import Invoice, InvoiceItem
from app.models import Order

@bp_api_admin.route('/new', methods=['POST'])
@roles_required('admin')
def create_invoice():
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
    invoice_items = []
    invoice.when_created = datetime.now()
    for order in orders:
        order.invoice = invoice
        invoice_items += [
            InvoiceItem(invoice=invoice, product=order_product.product, 
                    price=order_product.price, quantity=order_product.quantity)
            for order_product in order.order_products]

    db.session.add(invoice)
    db.session.add_all(invoice_items)
    db.session.commit()
    return jsonify({
        'status': 'success',
        'invoice_id': invoice.id
    })

@bp_api_admin.route('/', defaults={'invoice_id': None})
@bp_api_admin.route('/<invoice_id>')
@roles_required('admin')
def get_invoices(invoice_id):
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

def get_invoice_order_products(invoice, usd_rate):
    order_products = map_reduce(
        [order_product for order in invoice.orders
            for order_product in order.order_products],
        keyfunc=lambda op: (
            op.product_id,
            op.product.name_english if op.product.name_english \
                else op.product.name,
            round(op.price * usd_rate, 2)),
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
    total = reduce(lambda acc, op: acc + op['subtotal'], order_products, 0)
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
    ws.cell(305, 5, total)
    ws.cell(311, 4, f"{round(total, 2)} USD")
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

@bp_api_admin.route('/<invoice_id>/excel/<float:usd_rate>')
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

@bp_api_admin.route('/excel/<float:usd_rate>')
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
