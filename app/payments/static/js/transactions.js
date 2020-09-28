var editor;
$(document).ready( function () {
    editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var transaction_id = Object.entries(data.data)[0][0];
            var target = Object.entries(data.data)[0][1];
            var url = '/api/v1/transaction/' + transaction_id;
            $.ajax({
                url: url,
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(target),
                success: data => {success(({data: [data]}))},
                error: error
            });
        },
        table: '#transactions',
        idSrc: 'id',
        fields: [
            {
                label: 'Orders', 
                name: 'orders',
                type: 'select2',
                opts: {
                    multiple: true
                }
            },
            {
                label: 'Payment method', 
                name: 'payment_method',
                type: 'select2'
            },
            {label: 'Amount', name: 'amount_original'},
            {
                label: 'Currency',
                name: 'currency_code',
                type: 'select2'
            },
            {
                label: 'Evidence',
                name: 'evidences',
                type: 'uploadMany',
                ajax: '/api/v1/transaction/evidence'
            }
        ]
    });
    editor.on("open", get_currencies);
    editor.on("open", get_orders_to_pay);
    editor.on("open", get_payment_methods);

    var table = $('#transactions').DataTable({
        dom: 'lfrBtip',
        buttons: [
            { extend: 'create', editor: editor, text: 'Create new payment request' },
        ],        
        ajax: {
            url: '/api/v1/transaction',
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
            {data: 'orders'},
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
                    url: '/api/v1/transaction/' + update.id,
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
        url: '/api/v1/transaction/' + row.data().id,
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

function get_currencies() {
    $.ajax({
        url: '/api/v1/currency',
        success: data => {
            editor.field('currency_code').update(Object.entries(data).map(c => c[0]));
        }
    })}

function get_orders_to_pay() {
    $.ajax({
        url: '/api/v1/order?status=pending',
        success: data => {
            editor.field('orders').update(data.map(o => o.id));
        }
    })
}

function get_payment_methods() {
    $.ajax({
        url: '/api/v1/transaction/method',
        success: data => {
            editor.field('payment_method').update(data.map(pm => ({
                'label': pm.name,
                'name': pm.id
            })));
        }
    })
}