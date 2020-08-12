$.fn.dataTable.ext.buttons.invoice = {
    action: function(e, dt, node, config) {
        create_invoice(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    var table = $('#orders').DataTable({
        dom: 'lfrBtip',
        buttons: [
            {extend: 'invoice', text: 'Create invoice'}
        ],
        ajax: {
            url: '/api/v1/admin/order',
            dataSrc: ''
        },
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'id'},
            {data: 'user'},
            {data: 'customer'},
            {data: 'total'},
            {data: 'when_created'}
        ],
        select: true
    });

    $('#orders tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // First close all open rows
            $('tr.shown').each(function() {
                table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            row.child( format(row, row.data()) ).show();
            tr.addClass('shown');
        }
    } );
});

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
            url: '/api/v1/admin/order_product?order_id=' + data.id,
            dataSrc: ''
        },
        columns: [
            {data: 'id'},
            {data: 'product'},
            {data: 'price'},
            {data: 'quantity'},
            {data: 'status'}
        ]
    });
    return order_details;
}

function create_invoice(rows) {
    $('.wait').show();
    var orders = rows.data().map(row => row.id).toArray();
    $.ajax({
        url: '/api/v1/admin/invoice/new',
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