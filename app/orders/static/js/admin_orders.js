var g_order_statuses;
var g_orders_table;

$.fn.dataTable.ext.buttons.invoice = {
    action: function(e, dt, node, config) {
        create_invoice(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    get_dictionaries()
        .then(init_orders_table);
    $('#orders tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = g_orders_table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // First close all open rows
            $('tr.shown').each(function() {
                g_orders_table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            row.child( format(row, row.data()) ).show();
            tr.addClass('shown');

            $('.btn-save').on('click', event => save_order(event.target, row));
            $('.btn-delete').on('click', event => delete_order(event.target, row));
        }
    } );
});

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
                complete: function() {
                    $('.wait').hide();
                },
                success: () => {
                    row.draw();
                },
                error: (response) => {
                    modal('Delete sale order error', response.responseText)
                }
            });
        }
    });
}

async function get_dictionaries() {
    g_order_statuses = await get_list('/api/v1/order/status');
}

function save_order(target, row) {
    var order_node = $(target).closest('.order-details');
    var new_status = $('#status', order_node).val();
    if (row.data().status != new_status) {
        modal(
            "Order status change", 
            "Are you sure you want to change order status to <" + new_status + ">?",
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
    var update = {
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
        complete: function() {
            $('.wait').hide();
        },
        success: function(data) {
            row.data(data).draw();
        }
    });
}

/**
 * Draws invoice details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    var order_details = $('.order-details')
        .clone()
        .show();
    $('#order-products', order_details).DataTable({
        ajax: {
            url: '/api/v1/admin/order/product?order_id=' + data.id,
            dataSrc: ''
        },
        columns: [
            {data: 'subcustomer'},
	        {data: 'buyout_date'},
            {data: 'product_id'},
            {data: 'product', class: 'wrapok'},
            {data: 'price'},
            {data: 'quantity'},
            {data: 'status'}
        ],
        createdRow: (row, data) => {
            if (!data.purchase) {
                $(row).addClass('orange-line');
            }
        }
    });
    $('#invoice-id', order_details).val(data.invoice_id);
    $('#invoice-input-group', order_details).click(() => window.location = '/admin/invoices');
    $('#shipping', order_details).val(data.shipping.name);
    $('#shipping-cost', order_details).val(data.shipping_krw);
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
    return order_details;
}

function create_invoice(rows) {
    $('.wait').show();
    var orders = rows.data().map(row => row.id).toArray();
    $.ajax({
        url: '/api/v1/admin/invoice/new/' + $('#usd_rate').val(),
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({order_ids: orders}),
        complete: function() {
            $('.wait').hide();
        },
        success: function (data) {
            modal(
                'Invoice', 
                'Invoice ' + data.invoice_id + ' is created for orders ' + orders.join()
                + '<br />' +
                '<a href="/admin/invoices">Goto Invoices</a>');
        },
        error: function (ex) {
            console.log(ex);
        }
    });  
}

function init_orders_table() {
    g_orders_table = $('#orders').DataTable({
        dom: 'lrBtip',
        buttons: [
            {
                extend: 'print',
                text: 'Print order',
                customize: window => {
                    window.location = g_orders_table.rows({selected: true}).data()[0].id + '?view=print'
                }
            },
            {extend: 'invoice', text: 'Create invoice'}
        ],
        ajax: {
            url: '/api/v1/admin/order',
            dataSrc: 'data'
        },
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {
                'orderable': false,
                'data': null,
                fnCreatedCell: function(cell, sData, oData, iRow, iCol) {
                    if (oData.comment) {
                        $(cell).html("" +
                            "<span " +
                            "    data-toggle=\"tooltip\" data-delay=\"{ show: 5000, hide: 3000}\"" +
                            "    style=\"color: blue; font-weight:bolder; font-size:large;\"" +
                            "    title=\"" + oData.comment + "\">C</span>");
                    } else {
                        $(cell).html('');
                    }      
                }
            },
            {
                "className":      'order-actions',
                "orderable":      false,
                "data":           null,
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_order(this);">Open</button> \
                    <button \
                        class="btn btn-sm btn-secondary btn-invoice" \
                        onclick="open_order_invoice(this);">Invoice</button>'
            },            
            {data: 'id'},
            {data: 'user'},
            {data: 'customer_name'},
            {data: 'subtotal_krw'},
            {data: 'shipping_krw'},
            {data: 'total_krw'},
            {data: 'status'},
            {data: 'payment_method'},
            {
                data: 'shipping',
                render: 'name' 
            },
            {data: 'purchase_date'},
            {data: 'when_created'},
            {data: 'when_changed'},
        ],
        columnDefs: [
            {
                targets: [10, 11, 12],
                render: (data, type, row, meta) => {
                    return format_date(new Date(data));
                }
            }
        ],
        order: [[13, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        createdRow: (row, data) => {
            if (data.status != 'shipped') {
                $('.btn-invoice', row).remove();
            }
        },
        initComplete: function () {
            // Apply the search
            this.api().columns().every(function() { 
                var column = this;
                $('td:nth-child(' + (this.index() + 1) + ') input', 
                    $(this.header()).closest('thead'))
                    .on( 'keyup change clear', function () {
                        if ( column.search() !== this.value ) {
                            column
                                .search( this.value )
                                .draw();
                        }
                    })
                    .val('');
            });
        }    
    });
}

function open_order(target) {
    window.location = g_orders_table.row($(target).parents('tr')).data().id;
}

function open_order_invoice(target) {
    window.location = '/api/v1/order/' + 
        g_orders_table.row($(target).parents('tr')).data().id +
        '/excel';
}
