from datetime import datetime
from functools import reduce
import os.path
from tempfile import NamedTemporaryFile

from more_itertools import map_reduce
import openpyxl

from flask import Response, abort, current_app, jsonify, request
from flask_security import roles_required

from sqlalchemy import or_

from app import db
from app.invoices import bp_api_admin
from app.invoices.models.invoice import Invoice
from app.invoices.models.invoice_item import InvoiceItem
from app.orders.models.order import Order
from app.tools import prepare_datatables_query, stream_and_close

@bp_api_admin.route('/new/<float:usd_rate>', methods=['POST'])
@roles_required('admin')
def create_invoice(usd_rate):
    '''Creates invoice for provided orders'''
    payload = request.get_json()
    if not payload or not payload['order_ids']:
        abort(Response("No orders were provided", status=400))
    orders = Order.query.filter(Order.id.in_(payload['order_ids'])).all()
    if not orders:
        abort(Response("No orders with provided IDs were found ", status=400))
    invoice = Invoice()
    # invoice_items = []
    invoice.when_created = datetime.now()
    cumulative_order_products = map_reduce(
        [order_product for order in orders
                       for order_product in order.order_products],
        keyfunc=lambda ii: (
            ii.product_id,
            ii.product.name_english if ii.product.name_english \
                else ii.product.name,
            ii.price),
        valuefunc=lambda op: op.quantity,
        reducefunc=sum
    )
    for order in orders:
        order.invoice = invoice

    db.session.add(invoice)
    db.session.add_all([
        InvoiceItem(invoice=invoice, product_id=op[0][0],
                    price=round(op[0][2] * usd_rate, 2),
                    quantity=op[1])
        for op in cumulative_order_products.items()])
    db.session.add(InvoiceItem(
        invoice=invoice, product_id="SHIPPING",
        price=round(reduce(lambda acc, o: acc + o.shipping_krw * usd_rate, orders, 0), 2),
        quantity=1))
    db.session.commit()
    return jsonify({
        'status': 'success',
        'invoice_id': invoice.id
    })

@bp_api_admin.route('/', defaults={'invoice_id': None}, strict_slashes=False)
@bp_api_admin.route('/<invoice_id>')
@roles_required('admin')
def get_invoices(invoice_id):
    '''
    Returns all or selected invoices in JSON:
    '''

    invoices = Invoice.query

    if invoice_id is not None:
        invoices = invoices.filter_by(id=invoice_id)
    else: # here we check whether request is filtered by DataTables
        if request.values.get('draw') is not None:
            invoices, records_total, records_filtered = prepare_datatables_query(
                invoices, request.values,
                or_(                
                    Invoice.id.like(f"%{request.values['search[value]']}%"),
                    Invoice.orders.any(Order.id.like(f"%{request.values['search[value]']}%")),
                    Invoice.customer.like(f"%{request.values['search[value]']}%"))
            )
            return jsonify({
                'draw': request.values['draw'],
                'recordsTotal': records_total,
                'recordsFiltered': records_filtered,
                'data': list(map(lambda entry: entry.to_dict(), invoices))
            })
        else: # By default we return only 100 invoices
            invoices = invoices.limit(10)
    

    return jsonify(list(map(lambda entry: entry.to_dict(), invoices)))

def get_invoice_order_products(invoice):
    cumulative_order_products = map_reduce(
        invoice.get_invoice_items(),
        keyfunc=lambda ii: (
            ii.product_id,
            ii.product.name_english if ii.product.name_english \
                else ii.product.name,
            ii.price),
        valuefunc=lambda op: op.quantity,
        reducefunc=sum
    )

    result = list(map(lambda ii: {
        'id': ii[0][0],
        'name': ii[0][1],
        'price': ii[0][2],
        'quantity': ii[1],
        'subtotal': ii[0][2] * ii[1]
    }, cumulative_order_products.items()))
    return result

def create_invoice_excel(reference_invoice):
    package_path = os.path.dirname(__file__) + '/..'
    invoice_wb = openpyxl.open(f'{package_path}/templates/invoice_template.xlsx')
    invoice_dict = reference_invoice.to_dict()
    order_products = get_invoice_order_products(reference_invoice)
    total = reduce(lambda acc, op: acc + op['subtotal'], order_products, 0)
    ws = invoice_wb.worksheets[0]
    pl = invoice_wb.worksheets[1]

    # Set invoice header
    ws.cell(7, 2, reference_invoice.id)
    ws.cell(7, 5, reference_invoice.when_created)
    ws.cell(13, 4, reference_invoice.customer)
    ws.cell(15, 2, reference_invoice.payee)
    # ws.cell(17, 2, reference_invoice.address_1)
    # ws.cell(19, 2, reference_invoice.address_2)
    ws.cell(17, 4, reference_invoice.orders[0].address)
    ws.cell(21, 4, '') # city
    ws.cell(23, 5, reference_invoice.orders[0].country.name)
    ws.cell(25, 4, reference_invoice.orders[0].phone)

    # Set packing list header
    pl.cell(7, 2, reference_invoice.id)
    pl.cell(7, 5, reference_invoice.when_created)
    pl.cell(13, 4, reference_invoice.customer)
    ws.cell(15, 2, reference_invoice.payee)
    pl.cell(17, 4, reference_invoice.orders[0].address)
    pl.cell(21, 4, '') # city
    pl.cell(23, 5, reference_invoice.orders[0].country.name)
    pl.cell(25, 4, reference_invoice.orders[0].phone)

    # Set invoice footer
    ws.cell(305, 5, total)
    ws.cell(311, 4, f"{round(total, 2)} USD")
    ws.cell(312, 2, f"{invoice_dict['weight']}g")

    # Set packing list footer
    pl.cell(311, 4, f"{reduce(lambda qty, op: qty + op['quantity'], order_products, 0)}psc")
    pl.cell(312, 2, f"{invoice_dict['weight']}g")

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
    file = NamedTemporaryFile()
    invoice_wb.save(file.name)
    file.seek(0)
    return file

@bp_api_admin.route('/<invoice_id>', methods=['POST'])
@roles_required('admin')
def save_invoice(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(Response(f"The invoice <{invoice_id}> was not found", status=404))
    payload = request.get_json()
    if not payload:
        abort(Response("No invoice data was provided", status=400))
    editable_attributes = ['customer', 'payee']
    for attr in editable_attributes:
        if payload.get(attr) and getattr(invoice, attr) != payload[attr]:
            setattr(invoice, attr, type(getattr(invoice, attr))(payload[attr]))
            invoice.when_changed = datetime.now()
    db.session.commit()
    return jsonify(invoice.to_dict())


@bp_api_admin.route('/<invoice_id>/excel')
@roles_required('admin')
def get_invoice_excel(invoice_id):
    '''
    Generates an Excel file for an invoice
    '''
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(Response(f"The invoice <{invoice_id}> was not found", status=404))
    if invoice.invoice_items_count == 0:
        abort(Response(f"The invoice <{invoice_id}> has no items", status=406))

    file = create_invoice_excel(reference_invoice=invoice)
    return current_app.response_class(stream_and_close(file), headers={
        'Content-Disposition': f'attachment; filename="{invoice_id}.xlsx"',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })

@bp_api_admin.route('/excel')
@roles_required('admin')
def get_invoice_cumulative_excel():
    '''
    Returns cumulative Excel of several invoices
    invoice IDs are provides as URL arguments
    Resulting Excel isn't saved anywhere
    '''
    cumulative_invoice = Invoice()
    for invoice_id in request.args.getlist('invoices'):
        invoice = Invoice.query.get(invoice_id)
        if not cumulative_invoice.customer:
            cumulative_invoice.customer = invoice.customer
        if not cumulative_invoice.payee and invoice.payee:
            cumulative_invoice.payee = invoice.payee
        cumulative_invoice.orders += invoice.orders

    file = create_invoice_excel(reference_invoice=cumulative_invoice)
    return current_app.response_class(stream_and_close(file), headers={
        'Content-Disposition': 'attachment; filename="cumulative_invoice.xlsx"',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })

@bp_api_admin.route('/<invoice_id>/item/<invoice_item_id>', methods=['POST'])
@roles_required('admin')
def save_invoice_item(invoice_id, invoice_item_id):
    '''
    Creates or modifies existing invoice item
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))
    invoice = Invoice.query.get(invoice_id)
    invoice_item = None
    if not invoice:
        abort(Response(f'No invoice <{invoice_id}> was found', status=404))
    if invoice_item_id != 'new':
        invoice_item = invoice.get_invoice_items().filter_by(id=invoice_item_id).first()
        if not invoice_item:
            abort(Response(f'No invoice item <{invoice_item_id}> was found', status=404))
    else:
        invoice_item = InvoiceItem(invoice=invoice, when_created=datetime.now())
    
    for key, value in payload.items():
        if getattr(invoice_item, key) != value:
            setattr(invoice_item, key, value)
            invoice_item.when_changed = datetime.now()
    if invoice_item_id == 'new':
        db.session.add(invoice_item)
    db.session.commit()
    return jsonify(invoice_item.to_dict())

@bp_api_admin.route('/<invoice_id>/item/<invoice_item_id>', methods=['DELETE'])
@roles_required('admin')
def delete_invoice_item(invoice_id, invoice_item_id):
    '''
    Deletes existing invoice item
    '''
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        abort(Response(f'No invoice <{invoice_id}> was found', status=404))
    invoice_item = invoice.get_invoice_items().filter_by(id=invoice_item_id).first()
    if not invoice_item:
        abort(Response(f'No invoice item<{invoice_item_id}> was found', status=404))
    db.session.delete(invoice_item)
    db.session.commit()
    return jsonify({
        'status': 'success'
    })
