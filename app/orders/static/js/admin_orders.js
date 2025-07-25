let g_filter_sources;
let g_countries;
let g_currencies;
let g_order_statuses;
let g_orders_table;
let g_payment_methods;
let g_shipping_methods;
// var g_boxes;

$(document).ready(function () {
    $('#usd-rate').closest('li').prependTo('#infobar');
    get_dictionaries()
        .then(init_orders_table);
    $('#orders tbody').on('click', 'td.details-control', function () {
        const tr = $(this).closest('tr');
        const row = g_orders_table.row(tr);

        if (row.child.isShown()) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // First close all open rows
            $('tr.shown').each(function () {
                g_orders_table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            // row.child( format(row, row.data()) ).show();
            format(row, row.data());
            tr.addClass('shown');

            $('.btn-save').on('click', event => save_order(event.target, row));
            $('.btn-delete').on('click', event => delete_order(event.target, row));
        }
    });
});

function consign(target) {
    const order = target.row(target).data().id;
    consign_step(`/api/v1/admin/shipping/consign/${order}`)
}

function consign_step(url) {
    if (!/\/api\//.exec(url)) {
        window.open(url);
        return;
    }
    $('.wait').show();
    $.ajax({
        url: url,
        complete: () => {
            $('.wait').hide();
        },
        success: (data) => {
            if (data.status == 'success') {
                modal(
                    'The consignment is submitted',
                    `The consignment ${data.consignment_id} is submitted`);
            } else if (data.status == 'next_step_available') {
                modal(
                    "The consignment is submitted",
                    `The consignment ${data.consignment_id} is submitted. ` +
                    `Do you want to perform next step: ${data.next_step_message}?`,
                    'confirmation'
                )
                .then((result) => {
                    if (result == 'yes') {
                        consign_step(data.next_step_url);
                    }
                });
            } else {
                modal('Consignment error', data.message);
            }
        },
        error: (response) => {
            modal('Consignment error', response.responseText);
        }
    })
}

function delete_order(_target, row) {
    modal(
        "Order delete",
        "Are you sure you want to delete order <" + row.data().id + ">?",
        "confirmation")
        .then(result => {
            if (result == 'yes') {
                $('.wait').show();
                $.ajax({
                    url: '/api/v1/admin/order/' + row.data().id,
                    method: 'delete',
                    complete: function () {
                        $('.wait').hide();
                    },
                    success: () => {
                        row.draw();
                    },
                    error: (response) => {
                        modal('Delete sale order error', response.responseText);
                    }
                });
            }
        });
}

async function get_dictionaries() {
    g_countries = await get_list('/api/v1/country');
    g_currencies = (await get_list('/api/v1/currency')).data;
    g_order_statuses = await get_list('/api/v1/order/status');
    g_payment_methods = (await get_payment_methods()).map(
        item => ({ text: item.name, ...item }));
    g_shipping_methods = (await get_list('/api/v1/shipping')).map(
        item => ({ text: item.name, ...item }));
    // g_boxes = await get_list('/api/v1/admin/shipping/box');
    g_filter_sources = {
        'country': g_countries.map(i => ({ id: i.id, text: i.name })),
        'status': g_order_statuses,
        'payment_method': g_payment_methods,
        'shipping': g_shipping_methods
    }
}

async function print_label(target) {
    const order = target.row(target).data();
    const shipping = g_shipping_methods.find(sm => sm.id === order.shipping.id);
    window.open(`${shipping.links.print_label}?order_id=${order.id}`);
}

function save_order(target, row) {
    const order_node = $(target).closest('.order-details');
    const new_status = $('#status', order_node).val();
    if (row.data().status != new_status) {
        modal(
            "Order status change",
            "Are you sure you want to change order status to &lt;" + new_status + "&gt;?",
            "confirmation")
            .then(result => {
                if (result == 'yes') {
                    save_order_action(order_node, row);
                }
            });
    } else {
        save_order_action(order_node, row);
    }
}

function save_order_action(order_node, row) {
    const update = {
        id: row.data().id,
        status: $('#status', order_node).val(),
        tracking_id: $('#tracking-id', order_node).val(),
        tracking_url: $('#tracking-url', order_node).val()
    };
    $('.wait').show();
    $.ajax({
        url: '/api/v1/admin/order/' + update.id,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify(update),
        complete: function () {
            $('.wait').hide();
        },
        success: function (data) {
            row.data(data.data[0]).draw();
        },
        error: xhr => {
            modal('Order save error', xhr.responseText);
        }
    });
}

/**
 * Draws order details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
async function format(row, data) {
    const order_details = $('.order-details')
        .clone()
        .show();
    row.child(order_details).show();
    $('#order-products', order_details).DataTable({
        ajax: {
            url: '/api/v1/admin/order/product?order_id=' + data.id,
            dataSrc: ''
        },
        columns: [
            { data: 'subcustomer' },
            { data: 'buyout_date' },
            { data: 'product_id' },
            { data: 'product', class: 'wrapok' },
            { data: 'price' },
            { data: 'quantity' },
            { data: 'status' }
        ],
        rowGroup: {
            dataSrc: 'subcustomer'
        },
        createdRow: (row, data) => {
            if (!data.purchase) {
                $(row).addClass('orange-line');
            }
        }
    });
    const order = await (await fetch('/api/v1/admin/order/' + data.id)).json()
    $('#invoice-id', order_details).val(data.invoice_id);
    $('#invoice-input-group', order_details).click(() => window.location = '/admin/invoices');
    $('#export-id', order_details).val(order.invoice_id ? order.invoice.export_id : null);
    $('#po-company', order_details).val(order.purchase_orders.length ?
        order.purchase_orders[0].company : null);
    $('#shipping', order_details).val(data.shipping.name);
    $('#subtotal', order_details).val(data.subtotal_krw.toLocaleString());
    $('#shipping-cost', order_details).val(data.shipping_krw.toLocaleString());
    $('#total', order_details).val(data.total_krw.toLocaleString());
    $('#status', order_details).select2({
        theme: "bootstrap",
        data: g_order_statuses.map(os => ({
            id: os,
            text: os,
            selected: data.status == os
        }))
    });
    $('#status', order_details).val(data.status);
    $('#tracking-id', order_details).val(data.tracking_id);
    $('#tracking-url', order_details).val(data.tracking_url);
    $('#comment', order_details).val(data.comment);
    $('#order-params', order_details).DataTable({
        data: Object.entries(order.params)
            .map((e) =>
                Object.entries(e[1]).map((s) => ({
                    type: e[0],
                    name: s[0],
                    value: s[1].replace("\n", "<br />"),
                }))
            )
            .flat(),
        rowGroup: { dataSrc: 'type' },
        columns: [
            { data: 'name' },
            { data: 'value' }
        ]
    });
    return order_details;
}

function create_invoice(rows, currency) {
    $('.wait').show();
    const orders = rows.data().map(row => row.id).toArray();
    $.ajax({
        url: `/api/v1/admin/invoice/new`,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({ 
            order_ids: orders,
            currency: currency,
            rate: $(`#${currency}-rate`).val() || 1
        }),
        complete: function () {
            $('.wait').hide();
        },
        success: function (data) {
            modal(
                'Invoice',
                'Invoice <a href="/admin/invoices/' + data.invoice_id + '">'
                + data.invoice_id + '</a> is created for orders ' + orders.join());
        },
        error: function (ex) {
            console.log(ex);
        }
    });
}

function edit_shipment(sender) {
    const editor = new $.fn.dataTable.Editor({
        ajax: {
            edit: {
                url: '/api/v1/admin/order/_id_',
                contentType: 'application/json',
                data: data => {
                    const obj = Object.entries(data.data)[0][1];
                    return JSON.stringify({
                        total_weight: obj.total_weight,
                        boxes: Object.entries(obj.boxes.split('\n'))
                            .map(e => {
                                const match = /(\d+):(\d+):(\d+)x(\d+)x(\d+)/.exec(e);
                                return {
                                    quantity: match[1],
                                    weight: match[2],
                                    length: match[3],
                                    width: match[4],
                                    height: match[5]
                                };
                            })
                    });
                }
            }
        },
        table: '#orders',
        idSrc: 'id',
        fields: [
            {
                name: 'total_weight',
                label: 'Total weight',
                labelInfo: 'Total weight of the order including shipping box (in grams)',
                data: (data, _a, _b) => data.total_weight + data.shipping_box_weight
            },
            {
                name: 'boxes',
                label: 'Boxes',
                labelInfo: 'Enter boxes information (one box per line) in a format: ' +
                    '<span style="color:blue;">Qty:Wght:LxWxH</span> where:<br/>' +
                    'Qty - quantity<br/>' +
                    'Wght - weight<br />' +
                    'L - length<br />' +
                    'W - width<br />' +
                    'H - height',
                type: 'textarea',
                data: (data, _t, _s) => {
                    return data.boxes.map(e => {
                        return e.quantity + ":" + e.weight + ":" +
                            e.length + "x" + e.width + "x" + e.height
                    })
                        .join("\n");
                }
            }
        ]
    });
    const order_row = g_orders_table.row($(sender).closest('tr'));
    editor.on('preSubmit', function (e, data, action) {
        for (let entry of Object.entries(data.data)[0][1].boxes.split('\n')) {
            const match = /(\d+):(\d+):(\d+)x(\d+)x(\d+)/.exec(entry);
            if (match === null) {
                this.error(`Box information '${entry}' doesn't match format Qty:Wght:LxWxH`);
                return false;
            }
        }
    });
    editor
        .edit(order_row, true, {
            title: 'Set shipment info',
            buttons: 'Update'
        });
}

function init_orders_table() {
    g_orders_table = $('#orders').DataTable({
        // dom: 'lfrBtip',
        lengthChange: false,
        buttons: [
            {
                extend: 'print',
                text: 'Print',
                autoPrint: false,
                customize: window => {
                    window.location = g_orders_table.rows({ selected: true }).data()[0].id + '?view=print'
                }
            },
            {
                extend: 'collection',
                text: 'Create invoice',
                buttons: g_currencies.map(currency => ({
                    extend: 'selected',
                    text: currency.name,
                    action: function (e, dt, node, config) {
                        create_invoice(dt.rows({ selected: true }), currency.code);
                    }
                }))
            },
            {
                extend: 'selected',
                text: 'Export to Excel',
                action: function (e, dt, node, config) {
                    open_order_invoice(dt.rows({ selected: true }));
                }
            },
            {
                extend: 'selected',
                text: 'Customs label',
                action: function (e, dt, node, config) {
                    open_order_customs_label(dt.rows({ selected: true }));
                }
            },
            {
                extend: 'collection',
                text: 'Set status',
                buttons: [g_order_statuses.map(s => ({
                    extend: 'selected',
                    text: s,
                    action: function (e, dt, node, config) {
                        set_status(dt.rows({ selected: true }), this.text());
                    }
                }))]
            },
            {
                extend: 'selected',
                text: 'Copy',
                action: function (e, dt, node, config) {
                    open_order_copy_from(dt.rows({ selected: true }));
                }
            },
            {
                extend: 'collection',
                name: 'shipping',
                text: 'Shipping',
                buttons: [
                    {
                        extend: 'selectedSingle',
                        text: 'Consign',
                        action: function(e, dt, node, config) {
                            consign(dt.rows({selected: true}));
                        }
                    },
                    {
                        extend: 'selectedSingle',
                        text: 'Print label',
                        action: function(e, dt, node, config) {
                            print_label(dt.rows({selected: true}));
                        }
                    }
                ]
            },
            'pageLength'
        ],
        ajax: {
            url: '/api/v1/admin/order',
            dataSrc: 'data'
        },
        rowId: 'id',
        searchBuilder: {},
        columns: [
            {
                "className": 'details-control',
                "orderable": false,
                "data": null,
                "defaultContent": ''
            },
            {
                'orderable': false,
                'data': null,
                fnCreatedCell: function (cell, sData, oData, iRow, iCol) {
                    let html = '';
                    if (oData.comment) {
                        html +=
                            "<span " +
                            "    data-toggle=\"tooltip\" data-delay=\"{ show: 5000, hide: 3000}\"" +
                            "    style=\"color: blue; font-weight:bolder; font-size:large;\"" +
                            "    title=\"" + oData.comment + "\">C</span>";
                    }
                    if (oData.outsiders.length) {
                        html +=
                            "<span " +
                            "    data-toggle=\"tooltip\" data-delay=\"{ show: 5000, hide: 3000}\"" +
                            "    style=\"color: orange; font-weight:bolder; font-size:large;\"" +
                            "    title=\"The order has outsiders:\n" + oData.outsiders.join("\n") + "\">O</span>";
                    }
                    if (oData.payment_pending) {
                        html +=
                            "<a href=\"/admin/payments?orders=" + oData.id + "\">" +
                            "   <span " +
                            "       data-toggle=\"tooltip\" data-delay=\"{ show: 5000, hide: 3000}\"" +
                            "       style=\"color: green; font-weight:bolder; font-size:large;\"" +
                            "       title=\"The payment for order is pending\">P</span>" +
                            "</a>";
                    }

                    $(cell).html(html);
                }
            },
            {
                className: 'order-actions',
                orderable: false,
                data: null,
                defaultContent: ` \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_order(this);">Open</button> \
                    <button \
                        class="btn btn-sm btn-secondary btn-shipment" \
                        onclick="edit_shipment(this);">Shipment</button>`
            },
            {
                name: 'id',
                data: 'id',
                render: (data, type, row, meta) => {
                    return "<a href=\"/admin/orders/products?order_id=" + data + "\">" +
                        data + "</a>";
                }
            },
            { data: 'user' },
            { data: 'customer_name' },
            { data: 'subtotal_krw' },
            { data: 'shipping_krw' },
            { data: 'total_krw' },
            { data: 'status' },
            { data: 'payment_method', orderable: false },
            { data: 'shipping', render: 'name', orderable: false },
            { data: 'country', render: 'name', orderable: false },
            {
                name: 'invoice_export_id',
                data: null,
                render: (data, type, row) => { return row.invoice ? row.invoice.export_id : null; }
            },
            { data: 'purchase_date' },
            {
                data: 'when_po_posted',
                orderable: false,
                render: (data, type, row, meta) => {
                    return data
                        ? "<a href=\"/admin/purchase/orders?id=" +
                        row.id.replace('ORD', 'PO') + "\">" +
                        dt_render_local_time(data, type, row) + "</a>"
                        : dt_render_local_time(data, type, row);
                }
            },
            { data: 'when_created' },
            { data: 'when_changed' },
        ],
        columnDefs: [
            {
                targets: [14, 16, 17],
                render: (data, type, row, meta) => {
                    return dt_render_local_time(data, type, row);
                }
            }
        ],
        order: [[16, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        createdRow: (row, data) => {
            if (data.status != 'packed') {
                $('.btn-shipment', row).remove();
            }
        },
        initComplete: function () {
            const table = this;
            this.api().buttons().container().appendTo('#orders_wrapper .col-sm-12:eq(0)');
            init_search(table, g_filter_sources)
                .then(() => init_table_filter(table));
        }
    })
    .on('select', function(e, dt, type, indexes) {
        const order = g_orders_table.rows(indexes).data()[0];
        if (order.shipping.is_consignable && order.status == 'packed') {
            g_orders_table.button('shipping:name').enable();
        } else {
            g_orders_table.button('shipping:name').disable();
        }
    });
}

function open_order(target) {
    window.location = g_orders_table.row($(target).parents('tr')).data().id;
}

function open_order_customs_label(target) {
    for (let i = 0; i < target.count(); i++) {
        window.open(target.data()[i].id + '/customs_label');
    }
}

function open_order_invoice(target) {
    let error = '';
    for (let i = 0; i < target.count(); i++) {
        if (target.data()[i].status == 'shipped') {
            window.open('/orders/' + target.data()[i].id + '/excel');
        } else {
            error += "Can't export order " +
                target.data()[i].id +
                " to Excel because it's not in 'shipped' status<br />"
        }
    }
    if (error != '') {
        modal('Order excel export error', error)
    }
}

function set_status(target, new_status) {
    if (target.count()) {
        modal(
            "Order status change",
            "Are you sure you want to change orders status to &lt;" + new_status + "&gt;?",
            "confirmation")
            .then(result => {
                if (result == 'yes') {
                    $('.wait').show();
                    let orders_left = target.count();
                    for (let i = 0; i < target.count(); i++) {
                        $.post({
                            url: '/api/v1/admin/order/' + target.data()[i].id,
                            dataType: 'json',
                            contentType: 'application/json',
                            data: JSON.stringify({ status: new_status }),
                        })
                            .always(() => {
                                orders_left--;
                                if (!orders_left) {
                                    $('.wait').hide();
                                }
                            })
                            .fail((xhr, status, error) => {
                                alert(xhr.responseText);
                            })
                            .done((data, status, xhr) => {
                                g_orders_table.row("#" + data.data[0].id).data(data.data[0]).draw();
                            });
                    }
                }
            });
    } else {
        alert('Nothing selected');
    }
}

function open_order_copy_from(rows) {
    if (rows.count() == 1) {
        window.location = '/orders/new?from_order=' + rows.data()[0].id;
    }
}