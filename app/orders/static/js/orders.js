$.fn.dataTable.ext.buttons.xls = {
    action: function(e, dt, node, config) {
        get_excel(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    get_dictionaries()
        .then(init_orders_table);
});

/**
 * Draws order details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    var order_details = $('.order-details')
        .clone()
        .show();
        $('#tracking-id', order_details).val(data.tracking_id);
        $('#tracking-url', order_details).val(data.tracking_url);
        $('#comment', order_details).val(data.comment);
        return order_details;
}

async function get_dictionaries() {
    g_order_statuses = await get_list('/api/v1/order/status');
    g_filter_sources = {
        'status': g_order_statuses
    };
}

function get_excel(rows) {
    $('.wait').show();
    if (rows.count() == 1) {
        window.open('/api/v1/admin/order/' + rows.data()[0].id + '/excel');
    } else {
        var orders = '';
        for (var i = 0; i < rows.count(); i++) {
            orders += 'orders=' + rows.data()[i].id + '&';
        }
        window.open('/api/v1/admin/order/excel?' + orders);
    }
    $('.wait').hide()
}

function init_orders_table() {
    $('#orders').DataTable({
        dom: 'lrBtip',
        ajax: {
            url: '/api/v1/order',
            error: xhr => { modal('No orders', xhr.responseText) },
            dataSrc: 'data'
        },
        buttons: [
            // { extend: 'xls', text: 'Download' }
        ],
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
                // "defaultContent": ''
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_order(this);">Open</button> \
                    <button \
                        class="btn btn-sm btn-secondary btn-invoice" \
                        onclick="open_order_invoice(this);">Invoice</button>'
            },
            {data: 'id'},
            {data: 'customer_name'},
            {data: 'total_krw'},
            {data: 'total_rur'},
            {data: 'total_usd'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[8, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        createdRow: (row, data) => {
            if (data.status != 'shipped') {
                $('.btn-invoice', row).remove();
            }
        },
        initComplete: function() { init_search(this, g_filter_sources) }
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
            var order_details = format(row, row.data());
            row.child( order_details ).show();

            tr.addClass('shown');
        }
    } );

}

function open_order(target) {
    window.location = g_orders_table.row($(target).parents('tr')).data().id;
}

function open_order_invoice(target) {
    window.location = '/api/v1/order/' + 
        g_orders_table.row($(target).parents('tr')).data().id +
        '/excel';
}
