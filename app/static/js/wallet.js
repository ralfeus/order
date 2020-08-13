$.fn.dataTable.ext.buttons.create = {
    action: function(e, dt, node, config) {
        window.location = '/wallet/new';
    }
};

$(document).ready( function () {
    var table = $('#transactions').DataTable({
        dom: 'lfrBtip',
        buttons: [
            { extend: 'create', text: 'Create new transaction' },
        ],        
        ajax: {
            url: '/api/transaction',
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
            {data: 'order_id'},
            {data: 'payment_method'},
            {data: 'amount_original_string'},
            {data: 'amount_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[7, 'desc']],
        select: true
    });

    $('#transactions tbody').on('click', 'td.details-control', function () {
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
            $('.btn-save').on('click', function() {
                var transaction_node = $(this).closest('.transaction-details');
                var update = {
                    id: row.data().id,
                    amount: $('#amount', transaction_node).val(),
                    evidence: $('#evidence', transaction_node).val()
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/transaction/' + update.id,
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
                })
            });
            $('.btn-cancel').on('click', function() {cancel(row)});
        }
    } );
});

/**
 * Draws order product details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    var transaction_details = $('.transaction-details')
        .clone()
        .show(); 
    $('#evidence', transaction_details).attr('src', data.evidence_image);
    return transaction_details;
}

/**
 * Cancels transaction request
 * @param {*} target - table rows representing orders whose status is to be changed
 * @param {string} status - new status
 */
function cancel(row) {
    $('.wait').show();
    $.ajax({
        url: '/api/transaction/' + row.data().id,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            status: 'cancelled'
        }),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data) {
            row.data(data).draw();
        }
    });
}
