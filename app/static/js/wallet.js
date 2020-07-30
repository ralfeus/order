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
            {data: 'amount_original_string'},
            {data: 'amount_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],

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
    return '<div class="container transaction-details">'+
        '<div class="row container">'+
            '<label class="col-5" for="evidence">Payment proof:</label>'+
            // '<div class="col-4">' +
            //     '<div class="input-group">' +
            //         '<div class="input-group-prepend">' +
            //             '<span class="input-group-text">Amount:</span>' +
            //         '</div>' +
            //         '<input id="amount" class="form-control" value="' + data.amount_original + '" />' +
            //         '<div class="input-group-append">' +
            //             '<span class="input-group-text">' + data.currency_code + '</span>' +
            //         '</div>' +
            //     '</div>' +
            // '</div>' +
        '</div>' +
        '<div class="row container">' +
            '<img id="evidence" src="' + data.evidence_image + '" class="col-4" />' +
            '<div class="col-1">&nbsp;</div>' +
            '<div class="col-4">' +
                // '<input type="file" id="evidence" class="form-control" />' +
                // '<input type="button" class="button btn-primary btn-save col-2" value="Save" />' +
                '<input type="button" class="button btn-primary btn-cancel" value="Cancel transaction" />' +
            '</div>'+
    '</div>';
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
