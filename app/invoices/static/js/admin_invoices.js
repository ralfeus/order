var invoice_table;
$.fn.dataTable.ext.buttons.xls = {
    action: function(e, dt, node, config) {
        get_excel(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    invoice_table = $('#invoices').DataTable({
        dom: 'lfrBtip',
        ajax: {
            url: '/api/v1/admin/invoice'
        },
        buttons: [
            { extend: 'xls', text: 'Download' }
        ],
        columns: [
            {
                "className":      'invoice-actions',
                "orderable":      false,
                "data":           null,
                // "defaultContent": ''
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_invoice(this);">Open</button>'
            },
            {data: 'id'},
            {data: row => row.orders.join()},
            {data: 'total'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[4, 'desc']],
        select: true,
        serverSide: true,
        processing: true
    });

    // $('#invoices tbody').on('click', 'td.details-control', function () {
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
    //         var invoice_details = format(row, row.data());
    //         row.child( invoice_details ).show();

    //         tr.addClass('shown');
    //     }
    // } );
});

/**
 * Draws invoice details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
// function format ( row, data ) {
//     var invoice_details = $('.invoice-details')
//         .clone()
//         .show();
    // var editor = new $.fn.dataTable.Editor({
    //     table: '#invoice-items',
    //     idSrc: 'product_id',
    //     fields: [
    //         {label: 'Product ID', name: 'product_id'},
    //         {label: 'Price', name: 'price'},
    //         {label: 'Quantity', name: 'quantity'}
    //     ]
    // });
    // $('#invoice-items', invoice_details).on( 'click', 'td.editable', function (e) {
    //     editor.inline(this);
    // } );
    // $('#invoice-items', invoice_details).DataTable({
    //     dom: 'tp',
    //     ajax: {
    //         url: '/api/v1/admin/invoice/' + data.id,
    //         dataSrc: json => json[0].invoice_items
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
    // $('#total', invoice_details).val(data.total);
    // return invoice_details;
// }

function get_excel(rows) {
    $('.wait').show();
    if (rows.count() == 1) {
        window.open('/api/v1/admin/invoice/' + rows.data()[0].id + '/excel');
    } else {
        var invoices = '';
        for (var i = 0; i < rows.count(); i++) {
            invoices += 'invoices=' + rows.data()[i].id + '&';
        }
        window.open('/api/v1/admin/invoice/excel?' + invoices);
    }
    $('.wait').hide()
}

function open_invoice(target) {
    window.location = invoice_table.row($(target).parents('tr')).data().id;
}