var g_orders_table;
$.fn.dataTable.ext.buttons.invoice = {
    action: function(e, dt, node, config) {
        create_invoice(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    g_orders_table = $('#orders').DataTable({
        dom: 'lfrBtip',
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
                "className":      'order-actions',
                "orderable":      false,
                "data":           null,
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_order(this);">Open</button>'
            },            
            {data: 'id'},
            {data: 'user'},
            {data: 'customer'},
            {data: 'subtotal_krw'},
            {data: 'shipping_krw'},
            {data: 'total_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'},
        ],
        order: [[9, 'desc']],
        select: true,
        serverSide: true,
        processing: true
    });

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
        }
    } );
});

function save_order(target, row) {
    var order_node = $(target).closest('.order-details');
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
        ]
    });
    $('#invoice-id', order_details).val(data.invoice_id);
    $('#invoice-input-group', order_details).click(() => window.location = '/admin/invoices');
    $('#shipping', order_details).val(data.shipping.name);
    $('#shipping-cost', order_details).val(data.shipping_krw);
    $('#status', order_details).val(data.status);
    $('#tracking-id', order_details).val(data.tracking_id);
    $('#tracking-url', order_details).val(data.tracking_url);
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
            alert('Invoice ' + data.invoice_id + ' is created for orders ' + orders.join());
        },
        error: function (ex) {
            console.log(ex);
        }
    });  
}

function open_order(target) {
    window.location = g_orders_table.row($(target).parents('tr')).data().id;
}
