$.fn.dataTable.ext.buttons.xls = {
    action: function(e, dt, node, config) {
        get_excel(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    var table = $('#invoices').DataTable({
        dom: 'lfrBtip',
        ajax: {
            url: '/api/v1/admin/invoice',
            dataSrc: ''
        },
        buttons: [
            { extend: 'xls', text: 'Download' }
        ],
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'id'},
            {data: row => row.orders.join()},
            {data: 'total'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        select: true
    });

    $('#invoices tbody').on('click', 'td.details-control', function () {
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
    var invoice_details = $('.invoice-details')
        .clone()
        .show();
    return invoice_details;
}

function get_excel(rows) {
    $('.wait').show();
    for (var i = 0; i < rows.count(); i++) {
        window.open('/api/v1/admin/invoice/' + rows.data()[i].id + '/excel');
    }
    $('.wait').hide()
}