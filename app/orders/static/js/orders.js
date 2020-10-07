var order_table;
$.fn.dataTable.ext.buttons.xls = {
    action: function(e, dt, node, config) {
        get_excel(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    order_table = $('#orders').DataTable({
        dom: 'lfrBtip',
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
                "className":      'order-actions',
                "orderable":      false,
                "data":           null,
                // "defaultContent": ''
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_order(this);">Open</button>'
            },
            {data: 'id'},
            {data: 'customer'},
            {data: 'total_krw'},
            {data: 'total_rur'},
            {data: 'total_usd'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[6, 'desc']],
        select: true,
        serverSide: true,
        processing: true
    });

    // $('#orders tbody').on('click', 'td.details-control', function () {
    //     var tr = $(this).closest('tr');
    //     var row = table.row( tr );
 
    //     if ( row.child.isShown() ) {
    //         // This row is already open - close it
    //         row.child.hide();
    //         tr.removeClass('shown');
    //     }
    //     else {
    //         // First close all open rows
    //         $('tr.shown').each(function() {
    //             table.row(this).child.hide();
    //             $(this).removeClass('shown');
    //         })
    //         // Open this row
    //         var order_details = format(row, row.data());
    //         row.child( order_details ).show();

    //         tr.addClass('shown');
    //     }
    // } );
});

/**
 * Draws order details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
// function format ( row, data ) {
//     var order_details = $('.order-details')
//         .clone()
//         .show();
    // var editor = new $.fn.dataTable.Editor({
    //     table: '#order-items',
    //     idSrc: 'product_id',
    //     fields: [
    //         {label: 'Product ID', name: 'product_id'},
    //         {label: 'Price', name: 'price'},
    //         {label: 'Quantity', name: 'quantity'}
    //     ]
    // });
    // $('#order-items', order_details).on( 'click', 'td.editable', function (e) {
    //     editor.inline(this);
    // } );
    // $('#order-items', order_details).DataTable({
    //     dom: 'tp',
    //     ajax: {
    //         url: '/api/v1/admin/order/' + data.id,
    //         dataSrc: json => json[0].order_items
    //     },
    //     columns: [
    //         {data: 'product_id', className: 'editable'},
    //         {data: 'name', class: 'wrapok'},
    //         {data: 'price', className: 'editable'},
    //         {data: 'quantity', className: 'editable'},
    //         {data: 'subtotal'}
    //     ],
    //     select: true
    // });
    // $('#total', order_details).val(data.total);
    // return order_details;
// }

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

function open_order(target) {
    window.location = order_table.row($(target).parents('tr')).data().id;
}